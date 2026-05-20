# Architecture
Multi-service compose stack: litellm proxy, fastapi backend, postgres, redis, nginx.
Nginx routes all external traffic. LiteLLM is the AI gateway for all upstream services.
Postgres is the primary datastore. All services share the compose default network.
