FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ibapi is not on PyPI. Install from official IBKR wheel.
# Download from: https://interactivebrokers.github.io/
# For now, ibapi is optional (only needed when IB Gateway is connected).
RUN pip install --no-cache-dir ibapi 2>/dev/null || echo "ibapi not available on PyPI, IB features disabled until manually installed"

# PyTorch CPU-only (slim, ~200MB instead of 2GB).
# For GPU inference, mount a CUDA-enabled torch from the host.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
