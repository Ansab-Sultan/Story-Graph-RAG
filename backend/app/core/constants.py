"""Static constants shared across the backend."""

GRAPH_EXTRACTION_INSTRUCTIONS = """\
You are extracting a knowledge graph from a narrative story.

Node type conventions:
- Use UPPERCASE_SNAKE_CASE for all node types (e.g., CHARACTER, PLACE, MAGICAL_ARTIFACT)
- Be specific: prefer WEAPON over OBJECT, KINGDOM over PLACE when the text warrants it
- Always include a 'description' property with a brief summary

Relationship type conventions:
- Use UPPERCASE_SNAKE_CASE for all relationship types (e.g., FRIENDS_WITH, RULES_OVER)
- Capture the directional nature: (Character)-[BETRAYED]->(Character)
- Be specific: prefer MENTOR_OF over FRIENDS_WITH when appropriate
- Always include a 'description' property explaining the relationship context

Extract ALL meaningful entities and relationships you find. Do not limit yourself
to predefined categories. If a character wields a sword, create the WIELDS relationship.
If a prophecy foretells an event, create FORETELLS. Be thorough.
"""

SUPPORTED_EXTENSIONS = frozenset({".pdf", ".txt"})
DEFAULT_CORS_ORIGINS = ("*",)
DEFAULT_UPLOAD_DIR = "/tmp/story_graphrag_uploads"
DEFAULT_VECTOR_CHUNK_SIZE = 600
DEFAULT_VECTOR_CHUNK_OVERLAP = 100
DEFAULT_GRAPH_CHUNK_SIZE = 9000
DEFAULT_GRAPH_CHUNK_OVERLAP = 1000
DEFAULT_QUERY_TOP_K = 4
DEFAULT_SSE_POLL_INTERVAL_SECONDS = 0.5
DEFAULT_REDIS_LOCK_KEY = "story-graphrag:ingestion-lock"
DEFAULT_CHECKPOINT_COLLECTION_NAME = "langgraph_checkpoints"
DEFAULT_CHECKPOINT_WRITES_COLLECTION_NAME = "langgraph_checkpoint_writes"
DEFAULT_CHAT_TITLE_MAX_LENGTH = 80
DEFAULT_CHAT_PREVIEW_MAX_LENGTH = 120
DEFAULT_CHAT_PROMPT_HISTORY_MESSAGES = 12
DEFAULT_INFRASTRUCTURE_TIMEOUT_SECONDS = 2.0
GRAPH_ENTITY_LABEL = "Entity"
