"""Static constants shared across the backend."""

DEFAULT_ALLOWED_NODE_TYPES = (
    "CHARACTER",
    "PLACE",
    "EVENT",
    "OBJECT",
    "THEME",
)

DEFAULT_ALLOWED_RELATIONSHIP_TYPES = (
    "FRIENDS_WITH",
    "ENEMY_OF",
    "LOVES",
    "BETRAYED",
    "KILLED",
    "PRESENT_AT",
    "CAUSED",
    "LOCATED_IN",
    "LOYAL_TO",
)

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".txt"})
DEFAULT_CORS_ORIGINS = ("http://localhost:5173",)
DEFAULT_UPLOAD_DIR = "/tmp/story_graphrag_uploads"
DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 100
DEFAULT_QUERY_TOP_K = 4
DEFAULT_SSE_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_REDIS_LOCK_KEY = "story-graphrag:ingestion-lock"
GRAPH_ENTITY_LABEL = "Entity"

