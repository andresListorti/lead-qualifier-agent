# Simple view / Vista simple

`index.html` is a dependency-free page served by the API at `/`. It is a plain client of the
same public endpoints (`/health`, `POST /leads`, and an unauthenticated `GET /leads` to show the
401). Every HTTP call it makes is listed on the page with headers, body and a curl equivalent.
The technical view stays at `/docs` (Swagger); each view links to the other.

`index.html` es una página sin dependencias que la API sirve en `/`. Usa los mismos endpoints
públicos y muestra cada pedido HTTP real. La vista técnica sigue en `/docs`.
