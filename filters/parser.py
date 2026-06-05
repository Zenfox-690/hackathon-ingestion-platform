def parse_filters(filters):

    positive = []
    negative = []

    for keyword in filters:

        keyword = keyword.strip().lower()

        if keyword.startswith("-"):

            negative.append(
                keyword[1:]
            )

        else:

            positive.append(
                keyword.replace("+", "")
            )

    return positive, negative