"""Island model optimizer with DE + PSO + migration.

Implements multiple populations ("islands") running different algorithms
concurrently, with periodic migration of best solutions between islands.
Uses the C evaluator for speed.
"""

import numpy as np
from typing import Callable, List, Tuple


def _de_step(pop: np.ndarray, fitness: np.ndarray, bounds_lo: np.ndarray,
             bounds_hi: np.ndarray, evaluate: Callable, strategy: str,
             F: float, CR: float, rng: np.random.RandomState) -> Tuple[np.ndarray, np.ndarray]:
    """One generation of Differential Evolution."""
    n_pop, n_dim = pop.shape
    new_pop = pop.copy()
    new_fit = fitness.copy()

    best_idx = np.argmin(fitness)

    for i in range(n_pop):
        # Select 3 distinct random individuals (not i)
        candidates = [j for j in range(n_pop) if j != i]
        a, b, c = rng.choice(candidates, 3, replace=False)

        if strategy == 'best1bin':
            mutant = pop[best_idx] + F * (pop[a] - pop[b])
        elif strategy == 'rand1bin':
            mutant = pop[a] + F * (pop[b] - pop[c])
        elif strategy == 'currenttobest1bin':
            mutant = pop[i] + F * (pop[best_idx] - pop[i]) + F * (pop[a] - pop[b])
        else:  # rand2bin
            d = rng.choice([j for j in candidates if j not in (a, b, c)])
            mutant = pop[a] + F * (pop[b] - pop[c]) + F * (pop[best_idx] - pop[d])

        # Binomial crossover
        trial = pop[i].copy()
        j_rand = rng.randint(n_dim)
        for j in range(n_dim):
            if rng.rand() < CR or j == j_rand:
                trial[j] = mutant[j]

        # Clip to bounds
        trial = np.clip(trial, bounds_lo, bounds_hi)

        # Selection
        f_trial = evaluate(trial)
        if np.isfinite(f_trial) and f_trial < fitness[i]:
            new_pop[i] = trial
            new_fit[i] = f_trial

    return new_pop, new_fit


def _pso_step(pos: np.ndarray, vel: np.ndarray, fitness: np.ndarray,
              pbest_pos: np.ndarray, pbest_fit: np.ndarray,
              gbest_pos: np.ndarray, bounds_lo: np.ndarray,
              bounds_hi: np.ndarray, evaluate: Callable,
              w: float, c1: float, c2: float,
              rng: np.random.RandomState) -> Tuple[np.ndarray, np.ndarray, np.ndarray,
                                                     np.ndarray, np.ndarray, np.ndarray]:
    """One generation of Particle Swarm Optimization."""
    n_pop, n_dim = pos.shape

    r1 = rng.rand(n_pop, n_dim)
    r2 = rng.rand(n_pop, n_dim)

    # Update velocity
    vel = w * vel + c1 * r1 * (pbest_pos - pos) + c2 * r2 * (gbest_pos - pos)

    # Velocity clamping
    v_max = 0.3 * (bounds_hi - bounds_lo)
    vel = np.clip(vel, -v_max, v_max)

    # Update position
    pos = pos + vel
    pos = np.clip(pos, bounds_lo, bounds_hi)

    # Evaluate
    new_fitness = np.array([evaluate(pos[i]) for i in range(n_pop)])

    # Update personal bests
    improved = np.isfinite(new_fitness) & (new_fitness < pbest_fit)
    pbest_pos[improved] = pos[improved]
    pbest_fit[improved] = new_fitness[improved]

    # Update global best
    best_idx = np.argmin(pbest_fit)
    gbest_pos = pbest_pos[best_idx].copy()

    return pos, vel, new_fitness, pbest_pos, pbest_fit, gbest_pos


class Island:
    """A single island running one optimization algorithm."""

    def __init__(self, algorithm: str, pop_size: int, n_dim: int,
                 bounds_lo: np.ndarray, bounds_hi: np.ndarray,
                 evaluate: Callable, seed: int, **kwargs):
        self.algorithm = algorithm
        self.evaluate = evaluate
        self.bounds_lo = bounds_lo
        self.bounds_hi = bounds_hi
        self.rng = np.random.RandomState(seed)
        self.n_dim = n_dim
        self.kwargs = kwargs

        # Initialize population
        self.pop = bounds_lo + self.rng.rand(pop_size, n_dim) * (bounds_hi - bounds_lo)
        self.fitness = np.array([evaluate(self.pop[i]) for i in range(pop_size)])

        # PSO-specific state
        if algorithm.startswith('pso'):
            self.vel = self.rng.randn(pop_size, n_dim) * 0.1 * (bounds_hi - bounds_lo)
            self.pbest_pos = self.pop.copy()
            self.pbest_fit = self.fitness.copy()
            best_idx = np.argmin(self.fitness)
            self.gbest_pos = self.pop[best_idx].copy()

        self.generation = 0

    @property
    def best_fitness(self):
        return np.min(self.fitness)

    @property
    def best_individual(self):
        return self.pop[np.argmin(self.fitness)].copy()

    def evolve(self, n_generations: int = 1):
        """Run n generations of the algorithm."""
        for _ in range(n_generations):
            if self.algorithm.startswith('de'):
                strategy = self.algorithm.split('_', 1)[1] if '_' in self.algorithm else 'best1bin'
                F = self.kwargs.get('F', 0.7)
                CR = self.kwargs.get('CR', 0.9)
                self.pop, self.fitness = _de_step(
                    self.pop, self.fitness, self.bounds_lo, self.bounds_hi,
                    self.evaluate, strategy, F, CR, self.rng)

            elif self.algorithm.startswith('pso'):
                w = self.kwargs.get('w', 0.7)
                c1 = self.kwargs.get('c1', 1.5)
                c2 = self.kwargs.get('c2', 1.5)
                (self.pop, self.vel, self.fitness,
                 self.pbest_pos, self.pbest_fit, self.gbest_pos) = _pso_step(
                    self.pop, self.vel, self.fitness,
                    self.pbest_pos, self.pbest_fit, self.gbest_pos,
                    self.bounds_lo, self.bounds_hi, self.evaluate,
                    w, c1, c2, self.rng)

            self.generation += 1

    def inject(self, individual: np.ndarray, fitness: float):
        """Replace the worst individual with a migrant."""
        worst_idx = np.argmax(self.fitness)
        if fitness < self.fitness[worst_idx]:
            self.pop[worst_idx] = individual.copy()
            self.fitness[worst_idx] = fitness
            if hasattr(self, 'pbest_fit') and fitness < self.pbest_fit[worst_idx]:
                self.pbest_pos[worst_idx] = individual.copy()
                self.pbest_fit[worst_idx] = fitness


def run_archipelago(evaluate: Callable, bounds: list,
                    n_islands: int = 8, pop_per_island: int = 25,
                    n_generations: int = 300, migrate_every: int = 30,
                    seed: int = 42, verbose: bool = True) -> Tuple[np.ndarray, float]:
    """Run an archipelago of islands with periodic migration.

    Creates a diverse set of islands (mix of DE strategies + PSO),
    evolves them independently, and periodically migrates the best
    solution from each island to a random neighbor.
    """
    n_dim = len(bounds)
    lo = np.array([b[0] for b in bounds])
    hi = np.array([b[1] for b in bounds])

    # Create diverse islands
    island_configs = [
        ('de_best1bin', {'F': 0.7, 'CR': 0.9}),
        ('de_rand1bin', {'F': 0.8, 'CR': 0.9}),
        ('de_currenttobest1bin', {'F': 0.6, 'CR': 0.85}),
        ('de_best1bin', {'F': 0.5, 'CR': 0.95}),
        ('pso', {'w': 0.7, 'c1': 1.5, 'c2': 1.5}),
        ('pso', {'w': 0.5, 'c1': 2.0, 'c2': 2.0}),
        ('de_rand1bin', {'F': 0.9, 'CR': 0.7}),
        ('de_currenttobest1bin', {'F': 0.8, 'CR': 0.9}),
    ]

    islands = []
    for i in range(n_islands):
        algo, kwargs = island_configs[i % len(island_configs)]
        islands.append(Island(algo, pop_per_island, n_dim, lo, hi,
                              evaluate, seed=seed + i * 1000, **kwargs))

    if verbose:
        best_f = min(isl.best_fitness for isl in islands)
        print(f'  Init: best={best_f:.4f}', flush=True)

    # Evolution loop
    global_best_x = None
    global_best_f = np.inf

    for gen in range(0, n_generations, migrate_every):
        # Evolve each island
        for isl in islands:
            isl.evolve(migrate_every)

        # Update global best
        for isl in islands:
            if isl.best_fitness < global_best_f:
                global_best_f = isl.best_fitness
                global_best_x = isl.best_individual

        # Migration: ring topology — each island sends best to next
        migrants = [(isl.best_individual, isl.best_fitness) for isl in islands]
        for i in range(n_islands):
            target = (i + 1) % n_islands
            islands[target].inject(migrants[i][0], migrants[i][1])

        if verbose:
            algo_bests = [(isl.algorithm, isl.best_fitness) for isl in islands]
            algo_bests.sort(key=lambda x: x[1])
            top3 = ', '.join(f'{a}:{f:.2f}' for a, f in algo_bests[:3])
            print(f'  Gen {gen + migrate_every:4d}: best={global_best_f:.4f}  [{top3}]', flush=True)

    return global_best_x, global_best_f
