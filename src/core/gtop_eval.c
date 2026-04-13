/*
 * gtop_eval.c — Fast C evaluation for GTOP benchmark problems.
 *
 * Self-contained: JPL low-precision ephemeris, Lambert solver,
 * Kepler propagation, flyby rotation, Cassini1 + Cassini2 objectives.
 *
 * Compile: cc -O3 -shared -fPIC -o gtop_eval.dylib gtop_eval.c -lm
 *
 * All units: km, km/s, seconds, radians (unless noted).
 */

#include <math.h>
#include <string.h>

/* ---- Constants ---- */

#define MU_SUN    1.32712440018e11   /* km^3/s^2 (GTOP v2) */
#define AU_KM     149597870.691      /* km (GTOP v2) */
#define DEG2RAD   (M_PI / 180.0)
#define PENALTY   1e6

/* Body indices */
#define MERCURY 0
#define VENUS   1
#define EARTH   2
#define MARS    3
#define JUPITER 4
#define SATURN  5

/* Body mu (km^3/s^2) */
static const double BODY_MU[] = {
    22032.0, 324859.0, 398600.4418, 42828.0, 126686534.0, 37931187.0
};

/* Body radius (km) */
static const double BODY_RADIUS[] = {
    2440.0, 6052.0, 6378.0, 3397.0, 71492.0, 60330.0
};

/* Safe radius factor */
static const double BODY_SAFE[] = {
    1.1, 1.1, 1.1, 1.1, 9.0, 1.1
};

/* JPL LP ephemeris coefficients: [a0, adot, e0, edot, I0, Idot, L0, Ldot, w0, wdot, O0, Odot] */
static const double EPHEM[6][12] = {
    /* Mercury */ { 0.38709927, 0.00000037, 0.20563593, 0.00001906, 7.00497902, -0.00594749,
                    252.25032350, 149472.67411175, 77.45779628, 0.16047689, 48.33076593, -0.12534081 },
    /* Venus */   { 0.72333566, 0.00000390, 0.00677672, -0.00004107, 3.39467605, -0.00078890,
                    181.97909950, 58517.81538729, 131.60246718, 0.00268329, 76.67984255, -0.27769418 },
    /* Earth */   { 1.00000261, 0.00000562, 0.01671123, -0.00004392, -0.00001531, -0.01294668,
                    100.46457166, 35999.37244981, 102.93768193, 0.32327364, 0.0, 0.0 },
    /* Mars */    { 1.52371034, 0.00001847, 0.09339410, 0.00007882, 1.84969142, -0.00813131,
                    -4.55343205, 19140.30268499, -23.94362959, 0.44441088, 49.55953891, -0.29257343 },
    /* Jupiter */ { 5.20288700, -0.00011607, 0.04838624, -0.00013253, 1.30439695, -0.00183714,
                    34.39644051, 3034.74612775, 14.72847983, 0.21252668, 100.47390909, 0.20469106 },
    /* Saturn */  { 9.53667594, -0.00125060, 0.05386179, -0.00050991, 2.48599187, 0.00193609,
                    49.95424423, 1222.49362201, 92.59887831, -0.41897216, 113.66242448, -0.28867794 },
};

/* Cassini1 EVVEJS sequence */
static const int CASSINI1_SEQ[] = { EARTH, VENUS, VENUS, EARTH, JUPITER, SATURN };

/* ---- Vector operations ---- */

static inline double v3_norm(const double *v) {
    return sqrt(v[0]*v[0] + v[1]*v[1] + v[2]*v[2]);
}

static inline double v3_dot(const double *a, const double *b) {
    return a[0]*b[0] + a[1]*b[1] + a[2]*b[2];
}

static inline void v3_cross(const double *a, const double *b, double *out) {
    out[0] = a[1]*b[2] - a[2]*b[1];
    out[1] = a[2]*b[0] - a[0]*b[2];
    out[2] = a[0]*b[1] - a[1]*b[0];
}

static inline void v3_sub(const double *a, const double *b, double *out) {
    out[0] = a[0] - b[0]; out[1] = a[1] - b[1]; out[2] = a[2] - b[2];
}

static inline void v3_add(const double *a, const double *b, double *out) {
    out[0] = a[0] + b[0]; out[1] = a[1] + b[1]; out[2] = a[2] + b[2];
}

static inline void v3_scale(const double *v, double s, double *out) {
    out[0] = v[0]*s; out[1] = v[1]*s; out[2] = v[2]*s;
}

/* ---- Stumpff functions ---- */

static double stumpff_c2(double psi) {
    if (psi > 1e-6) return (1.0 - cos(sqrt(psi))) / psi;
    else if (psi < -1e-6) return (cosh(sqrt(-psi)) - 1.0) / (-psi);
    else return 0.5;
}

static double stumpff_c3(double psi) {
    if (psi > 1e-6) { double sp = sqrt(psi); return (sp - sin(sp)) / (psi * sp); }
    else if (psi < -1e-6) { double sp = sqrt(-psi); return (sinh(sp) - sp) / ((-psi) * sp); }
    else return 1.0 / 6.0;
}

/* ---- Kepler equation solver ---- */

static double solve_kepler(double M, double e) {
    double E = M + e * sin(M);
    for (int i = 0; i < 50; i++) {
        double dE = (M - E + e * sin(E)) / (1.0 - e * cos(E));
        E += dE;
        if (fabs(dE) < 1e-15) break;
    }
    return E;
}

/* ---- JPL LP ephemeris ---- */

static void jpl_lp_state(int body, double mjd2000, double *state) {
    /* state: [x,y,z,vx,vy,vz] in km, km/s, ecliptic J2000 */
    const double *c = EPHEM[body];
    double T = (mjd2000 - 0.5) / 36525.0;

    double a_au  = c[0]  + c[1]  * T;
    double e     = c[2]  + c[3]  * T;
    double I_deg = c[4]  + c[5]  * T;
    double L_deg = c[6]  + c[7]  * T;
    double w_deg = c[8]  + c[9]  * T;
    double O_deg = c[10] + c[11] * T;

    double omega_deg = w_deg - O_deg;
    double M_deg = L_deg - w_deg;

    double inc = I_deg * DEG2RAD;
    double Om  = O_deg * DEG2RAD;
    double om  = omega_deg * DEG2RAD;
    double M   = fmod(M_deg * DEG2RAD, 2.0 * M_PI);
    if (M < 0) M += 2.0 * M_PI;

    double E = solve_kepler(M, e);
    double a_km = a_au * AU_KM;
    double cosE = cos(E), sinE = sin(E);
    double sqrt1me2 = sqrt(1.0 - e * e);
    double denom = 1.0 - e * cosE;

    /* Perifocal frame */
    double x_p = a_km * (cosE - e);
    double y_p = a_km * sqrt1me2 * sinE;
    double n = sqrt(MU_SUN / (a_km * a_km * a_km));
    double vx_p = -a_km * n * sinE / denom;
    double vy_p = a_km * sqrt1me2 * n * cosE / denom;

    /* Rotation matrix */
    double cO = cos(Om), sO = sin(Om);
    double co = cos(om), so = sin(om);
    double ci = cos(inc), si = sin(inc);

    double R00 = cO*co - sO*so*ci, R01 = -cO*so - sO*co*ci;
    double R10 = sO*co + cO*so*ci, R11 = -sO*so + cO*co*ci;
    double R20 = so*si,             R21 = co*si;

    state[0] = R00*x_p + R01*y_p;
    state[1] = R10*x_p + R11*y_p;
    state[2] = R20*x_p + R21*y_p;
    state[3] = R00*vx_p + R01*vy_p;
    state[4] = R10*vx_p + R11*vy_p;
    state[5] = R20*vx_p + R21*vy_p;
}

/* ---- Lambert solver (universal variable + Stumpff) ---- */

static int solve_lambert(const double *r1, const double *r2, double tof, double mu,
                         double *v1_out, double *v2_out) {
    double r1m = v3_norm(r1), r2m = v3_norm(r2);
    double cross_z = r1[0]*r2[1] - r1[1]*r2[0];
    double cos_dnu = v3_dot(r1, r2) / (r1m * r2m);
    if (cos_dnu > 1.0) cos_dnu = 1.0;
    if (cos_dnu < -1.0) cos_dnu = -1.0;

    double sin_dnu = (cross_z >= 0) ? sqrt(1.0 - cos_dnu*cos_dnu) : -sqrt(1.0 - cos_dnu*cos_dnu);
    double A = sin_dnu * sqrt(r1m * r2m / (1.0 - cos_dnu));
    if (fabs(A) < 1e-14) return -1;

    double psi_low = -4.0 * M_PI * M_PI;
    double psi_up  =  4.0 * M_PI * M_PI;
    double psi = 0.0;

    double c2, c3, y, chi, tof_cur;

    for (int iter = 0; iter < 60; iter++) {
        c2 = stumpff_c2(psi);
        c3 = stumpff_c3(psi);
        y = r1m + r2m + A * (psi * c3 - 1.0) / sqrt(c2);

        if (A > 0 && y < 0) {
            while (y < 0) {
                psi += 0.1;
                c2 = stumpff_c2(psi);
                c3 = stumpff_c3(psi);
                y = r1m + r2m + A * (psi * c3 - 1.0) / sqrt(c2);
            }
        }

        chi = sqrt(y / c2);
        tof_cur = (chi*chi*chi * c3 + A * sqrt(y)) / sqrt(mu);

        if (fabs(tof_cur - tof) < 1e-8) break;

        /* Newton-Raphson with bisection fallback */
        double dtof;
        if (fabs(psi) > 1e-6)
            dtof = (chi*chi*chi * (c2 - 3*c3/(2*c2)) / (2*psi) +
                    3*c3*chi*A / (4*c2) + A*sqrt(c2)/(2*psi)) / sqrt(mu);
        else
            dtof = (sqrt(2.0)/40.0 * pow(y, 1.5) +
                    A/8.0 * (sqrt(y) + A*sqrt(1.0/(2.0*y)))) / sqrt(mu);

        if (fabs(dtof) < 1e-14) {
            if (tof_cur <= tof) psi_low = psi; else psi_up = psi;
            psi = (psi_low + psi_up) / 2.0;
        } else {
            double psi_new = psi + (tof - tof_cur) / dtof;
            if (psi_new < psi_low || psi_new > psi_up) {
                if (tof_cur <= tof) psi_low = psi; else psi_up = psi;
                psi = (psi_low + psi_up) / 2.0;
            } else {
                if (tof_cur <= tof) psi_low = psi; else psi_up = psi;
                psi = psi_new;
            }
        }
    }

    /* Lagrange coefficients */
    c2 = stumpff_c2(psi);
    c3 = stumpff_c3(psi);
    y = r1m + r2m + A * (psi * c3 - 1.0) / sqrt(c2);

    double f = 1.0 - y / r1m;
    double g = A * sqrt(y / mu);
    double g_dot = 1.0 - y / r2m;

    if (fabs(g) < 1e-14) return -1;

    v1_out[0] = (r2[0] - f*r1[0]) / g;
    v1_out[1] = (r2[1] - f*r1[1]) / g;
    v1_out[2] = (r2[2] - f*r1[2]) / g;
    v2_out[0] = (g_dot*r2[0] - r1[0]) / g;
    v2_out[1] = (g_dot*r2[1] - r1[1]) / g;
    v2_out[2] = (g_dot*r2[2] - r1[2]) / g;

    return 0;
}

/* ---- Kepler propagation (universal variable) ---- */

static int propagate_kepler(const double *r0, const double *v0, double dt, double mu,
                            double *r1, double *v1) {
    double r0m = v3_norm(r0);
    double v0m = v3_norm(v0);
    double energy = v0m*v0m / 2.0 - mu / r0m;
    double alpha = -2.0 * energy / mu;  /* 1/a */
    double vr0 = v3_dot(r0, v0) / r0m;

    /* Initial guess for chi */
    double chi;
    if (alpha > 1e-10) {
        chi = sqrt(mu) * dt * alpha;
    } else if (alpha < -1e-10) {
        double a = 1.0 / alpha;
        double arg = (-2.0 * mu * alpha * dt) /
                     (v3_dot(r0, v0) + (dt >= 0 ? 1 : -1) * sqrt(-mu * a) * (1.0 - r0m * alpha));
        if (arg <= 0) return -1;
        chi = (dt >= 0 ? 1 : -1) * sqrt(-a) * log(arg);
    } else {
        chi = sqrt(mu) * dt / r0m;  /* simple parabolic guess */
    }

    /* Newton-Raphson */
    double psi, c2, c3, r;
    for (int i = 0; i < 50; i++) {
        psi = chi * chi * alpha;
        c2 = stumpff_c2(psi);
        c3 = stumpff_c3(psi);
        r = chi*chi*c2 + vr0/sqrt(mu) * chi*(1.0 - psi*c3) + r0m*(1.0 - psi*c2);
        double f_chi = r0m*vr0/sqrt(mu) * chi*chi*c2 +
                       (1.0 - r0m*alpha) * chi*chi*chi*c3 + r0m*chi - sqrt(mu)*dt;
        double f_prime = r;
        if (fabs(f_prime) < 1e-14) break;
        double delta = f_chi / f_prime;
        chi -= delta;
        if (fabs(delta) < 1e-10) break;
    }

    psi = chi * chi * alpha;
    c2 = stumpff_c2(psi);
    c3 = stumpff_c3(psi);

    double f = 1.0 - chi*chi / r0m * c2;
    double g = dt - chi*chi*chi / sqrt(mu) * c3;
    r1[0] = f*r0[0] + g*v0[0];
    r1[1] = f*r0[1] + g*v0[1];
    r1[2] = f*r0[2] + g*v0[2];

    double r1m = v3_norm(r1);
    double f_dot = sqrt(mu) / (r1m * r0m) * chi * (psi*c3 - 1.0);
    double g_dot = 1.0 - chi*chi / r1m * c2;
    v1[0] = f_dot*r0[0] + g_dot*v0[0];
    v1[1] = f_dot*r0[1] + g_dot*v0[1];
    v1[2] = f_dot*r0[2] + g_dot*v0[2];

    return 0;
}

/* ---- Unpowered flyby (pykep fb_prop convention) ---- */

static void flyby_prop(const double *v_in_helio, const double *v_planet,
                       double mu_body, double rp, double beta,
                       double *v_out_helio) {
    double v_inf[3];
    v3_sub(v_in_helio, v_planet, v_inf);
    double vm = v3_norm(v_inf);
    if (vm < 1e-10) { memcpy(v_out_helio, v_in_helio, 3*sizeof(double)); return; }

    double e = 1.0 + rp * vm * vm / mu_body;
    double sinv = 1.0 / e;
    if (sinv > 1.0) sinv = 1.0;
    double delta = 2.0 * asin(sinv);

    /* Local frame: i = unit(v_inf), k = unit(v_inf x v_planet), j = k x i */
    double i_hat[3], k_hat[3], j_hat[3];
    v3_scale(v_inf, 1.0/vm, i_hat);
    v3_cross(i_hat, v_planet, k_hat);
    double km = v3_norm(k_hat);
    if (km < 1e-10) {
        double pole[3] = {0, 0, 1};
        v3_cross(i_hat, pole, k_hat);
        km = v3_norm(k_hat);
    }
    v3_scale(k_hat, 1.0/km, k_hat);
    v3_cross(k_hat, i_hat, j_hat);

    double cd = cos(delta), sd = sin(delta), sb = sin(beta), cb = cos(beta);
    double v_inf_out[3];
    for (int i = 0; i < 3; i++)
        v_inf_out[i] = vm * (cd * i_hat[i] + sd * sb * j_hat[i] + sd * cb * k_hat[i]);

    v3_add(v_planet, v_inf_out, v_out_helio);
}

/* ---- Saturn orbit insertion ---- */

static double saturn_insertion_dv(double v_inf) {
    double rp = 108950.0, e_target = 0.98;
    double mu_sat = BODY_MU[SATURN];
    double vp_hyp = sqrt(v_inf*v_inf + 2.0*mu_sat/rp);
    double a_target = rp / (1.0 - e_target);
    double vp_orb = sqrt(mu_sat * (2.0/rp - 1.0/a_target));
    return fabs(vp_hyp - vp_orb);
}

/* ---- Cassini1 evaluate (pure MGA, 6 variables, GTOP ephemeris) ---- */

double cassini1_eval(const double *x) {
    /*
     * x[0]: t0 (MJD2000)
     * x[1..5]: T1..T5 (days)
     */
    double epochs[6];
    epochs[0] = x[0];
    for (int i = 0; i < 5; i++) epochs[i+1] = epochs[i] + x[i+1];

    /* Body states */
    double states[6][6];
    static const int seq[] = { EARTH, VENUS, VENUS, EARTH, JUPITER, SATURN };
    for (int i = 0; i < 6; i++)
        jpl_lp_state(seq[i], epochs[i], states[i]);

    /* Lambert for each leg */
    double v_dep[5][3], v_arr[5][3];
    for (int leg = 0; leg < 5; leg++) {
        double tof = x[leg+1] * 86400.0;
        if (solve_lambert(states[leg], states[leg+1], tof, MU_SUN,
                          v_dep[leg], v_arr[leg]) != 0)
            return PENALTY;
    }

    /* Departure v_inf */
    double vinf_dep[3];
    v3_sub(v_dep[0], states[0]+3, vinf_dep);
    double total_dv = v3_norm(vinf_dep);

    /* Powered flybys at rp_min */
    for (int i = 1; i <= 4; i++) {
        double vi[3], vo[3];
        v3_sub(v_arr[i-1], states[i]+3, vi);
        v3_sub(v_dep[i], states[i]+3, vo);
        double vim = v3_norm(vi), vom = v3_norm(vo);
        int body = seq[i];
        double rp_min = BODY_RADIUS[body] * BODY_SAFE[body];
        double mu_b = BODY_MU[body];

        double vp_in = sqrt(vim*vim + 2.0*mu_b/rp_min);
        double vp_out = sqrt(vom*vom + 2.0*mu_b/rp_min);
        double dv_fb = fabs(vp_out - vp_in);

        /* Bending feasibility */
        double cos_d = v3_dot(vi, vo) / (vim * vom);
        if (cos_d > 1.0) cos_d = 1.0;
        if (cos_d < -1.0) cos_d = -1.0;
        double delta_req = acos(cos_d);
        double e_in = 1.0 + rp_min * vim * vim / mu_b;
        double e_out = 1.0 + rp_min * vom * vom / mu_b;
        double s_in = 1.0/e_in; if (s_in > 1.0) s_in = 1.0;
        double s_out = 1.0/e_out; if (s_out > 1.0) s_out = 1.0;
        double delta_max = asin(s_in) + asin(s_out);
        if (delta_req > delta_max) {
            dv_fb += 0.5 * (vim + vom) * (delta_req - delta_max);
        }

        total_dv += dv_fb;
    }

    /* Saturn insertion */
    double vinf_sat[3];
    v3_sub(v_arr[4], states[5]+3, vinf_sat);
    total_dv += saturn_insertion_dv(v3_norm(vinf_sat));

    return total_dv;
}

/* ---- Cassini2 evaluate (MGA-1DSM, 22 variables, GTOP ephemeris) ---- */

double cassini2_eval(const double *x) {
    /*
     * x[0]: t0, x[1]: Vinf, x[2]: u, x[3]: v
     * x[4..8]: T1..T5, x[9..13]: eta1..eta5
     * x[14..17]: rp1..rp4 (body radii), x[18..21]: beta1..beta4
     */
    static const int seq[] = { EARTH, VENUS, VENUS, EARTH, JUPITER, SATURN };

    double t0 = x[0], vinf_mag = x[1], u = x[2], v = x[3];
    const double *tofs = x + 4;   /* T1..T5 in days */
    const double *etas = x + 9;   /* eta1..eta5 */
    const double *rps  = x + 14;  /* rp1..rp4 in body radii */
    const double *betas = x + 18; /* beta1..beta4 */

    /* Encounter epochs */
    double epochs[6];
    epochs[0] = t0;
    for (int i = 0; i < 5; i++) epochs[i+1] = epochs[i] + tofs[i];

    /* Planet states */
    double states[6][6];
    for (int i = 0; i < 6; i++)
        jpl_lp_state(seq[i], epochs[i], states[i]);

    /* Departure velocity */
    double theta = 2.0 * M_PI * u;
    double phi = acos(2.0 * v - 1.0) - M_PI / 2.0;
    double v_sc[3];
    v_sc[0] = states[0][3] + vinf_mag * cos(phi) * cos(theta);
    v_sc[1] = states[0][4] + vinf_mag * cos(phi) * sin(theta);
    v_sc[2] = states[0][5] + vinf_mag * sin(phi);

    double total_dv = vinf_mag;

    for (int leg = 0; leg < 5; leg++) {
        double tof_sec = tofs[leg] * 86400.0;
        double eta = etas[leg];
        double dt_coast = eta * tof_sec;
        double dt_lambert = (1.0 - eta) * tof_sec;
        if (dt_lambert < 1.0) return PENALTY;

        /* Ballistic coast */
        double r_dsm[3], v_bal[3];
        if (propagate_kepler(states[leg], v_sc, dt_coast, MU_SUN, r_dsm, v_bal) != 0)
            return PENALTY;

        /* Check finite */
        if (!isfinite(r_dsm[0]) || !isfinite(v_bal[0])) return PENALTY;

        /* Lambert from DSM to next body */
        double v_ls[3], v_le[3];
        if (solve_lambert(r_dsm, states[leg+1], dt_lambert, MU_SUN, v_ls, v_le) != 0)
            return PENALTY;
        if (!isfinite(v_ls[0]) || !isfinite(v_le[0])) return PENALTY;

        /* DSM cost */
        double dv_dsm[3];
        v3_sub(v_ls, v_bal, dv_dsm);
        double dsm = v3_norm(dv_dsm);
        if (!isfinite(dsm)) return PENALTY;
        total_dv += dsm;

        /* Flyby or arrival */
        if (leg < 4) {
            int body = seq[leg + 1];
            double rp_km = rps[leg] * BODY_RADIUS[body];
            flyby_prop(v_le, states[leg+1]+3, BODY_MU[body], rp_km, betas[leg], v_sc);
            if (!isfinite(v_sc[0])) return PENALTY;
        } else {
            double vinf_arr[3];
            v3_sub(v_le, states[5]+3, vinf_arr);
            total_dv += v3_norm(vinf_arr);
        }
    }

    return isfinite(total_dv) ? total_dv : PENALTY;
}
