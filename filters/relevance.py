def calculate_score(hackathon, filters):
	"""Compute a relevance score for a hackathon given user filters.

	Scoring heuristic:
	- Plain keyword: +2 for title match, +1 for description match
	- +keyword (required): 0 if not found (filter fails)
	- -keyword (excluded): 0 if found (filter fails)

	Returns an int score (0 means no match or filter failed).
	"""
	if not filters:
		return 0

	title = hackathon.get("name", "").lower()
	description = hackathon.get("description", "").lower()

	score = 0
	required_keywords = []
	excluded_keywords = []
	preferred_keywords = []

	for kw in filters:
		if not kw:
			continue

		k = kw.lower().strip()

		if k.startswith("+"):
			required_keywords.append(k[1:])
		elif k.startswith("-"):
			excluded_keywords.append(k[1:])
		else:
			preferred_keywords.append(k)

	# Check exclusions first
	for k in excluded_keywords:
		if k in title or k in description:
			return 0

	# Check required keywords
	for k in required_keywords:
		if k not in title and k not in description:
			return 0

	# Score preferred keywords
	for k in preferred_keywords:
		if k in title:
			score += 2
		if k in description:
			score += 1

	return score
