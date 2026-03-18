#!/bin/bash
# Download required SPICE kernels for orbital mechanics computations.
# Run this after cloning the repo.

KERNEL_DIR="$(dirname "$0")/../kernels"
mkdir -p "$KERNEL_DIR"

echo "Downloading SPICE kernels..."

# Leapseconds kernel
if [ ! -f "$KERNEL_DIR/naif0012.tls" ]; then
    echo "  naif0012.tls (leapseconds)..."
    curl -s -o "$KERNEL_DIR/naif0012.tls" \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls
fi

# Planetary constants
if [ ! -f "$KERNEL_DIR/pck00011.tpc" ]; then
    echo "  pck00011.tpc (planetary constants)..."
    curl -s -o "$KERNEL_DIR/pck00011.tpc" \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc
fi

# Planetary ephemeris (32 MB)
if [ ! -f "$KERNEL_DIR/de440s.bsp" ]; then
    echo "  de440s.bsp (planetary ephemeris, 32 MB)..."
    curl -s -o "$KERNEL_DIR/de440s.bsp" \
        https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp
fi

echo "Done. Kernels in $KERNEL_DIR:"
ls -lh "$KERNEL_DIR"
