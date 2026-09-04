"""Request bounds shared by the two reads that rank the embeddings index."""

#: Per-content-type cap, shared by ``GET /search`` and ``GET /semantic/related``.
#:
#: It bounds one group rather than a whole page, so it can afford to be generous:
#: a caller assembling its own mixed ranking out of the groups wants room to work
#: with.
MAX_SEARCH_ITEMS_PER_TYPE = 100
