FROM python:3.11-slim

WORKDIR /app

# Install system deps for spiceypy
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl && \
    rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download SPICE kernels
RUN mkdir -p kernels && \
    curl -sL -o kernels/naif0012.tls https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/naif0012.tls && \
    curl -sL -o kernels/pck00011.tpc https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/pck00011.tpc && \
    curl -sL -o kernels/de440s.bsp https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440s.bsp

# Copy application
COPY src/ src/

EXPOSE 8790

CMD ["python", "-m", "src.api.server"]
