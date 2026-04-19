"""Constants and limits for AI agents and steps."""

# --- LLM Max Token Limits ---

# Context Analyzer (Intent inference + entity mapping)
# It only outputs a JSON schema map with a few parameters
LLM_CONTEXT_ANALYZER_MAX_TOKENS = 1024

# Matching/Scoring Engine
# The score_and_rank outputs a structured JSON list of units & experts + a final answer string.
LLM_MATCHING_SCORE_RANK_MAX_TOKENS = 4096

# Chat answer generation
LLM_MATCHING_BUILD_ANSWER_MAX_TOKENS = 1024

# Chat title generator
# Just a brief 1-2 sentence max
LLM_TITLE_GENERATION_MAX_TOKENS = 120
