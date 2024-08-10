import base64
import gzip
import logging
import pickle
from datetime import datetime

from pydiscourse import DiscourseClient

logger = logging.getLogger()
deb = logger.debug
info = logger.info
warn = logger.warn
err = logger.error


def generate_post_winners(all_items: list) -> str:
    post = (
        "*This post is generated by the rafflebot!"
        + " All code is open source, please see https://github.com/vhs/raffle"
        + " to see how this is generated,"
        + " and how you can verify the results at home.*\n\n"
    )

    post += "<h1>Raffle Results</h1>\n\n"

    for item in all_items:
        post += f"**{item['description']}**\n"

        post += "\nWinners:\n"

        for i, entrant in enumerate(item["sorted_winner_list"]):
            if i < item["winners_count"]:
                post += generate_entry(i + 1, entrant, True)
            else:
                continue

        if len(item["sorted_winner_list"]) >= item["winners_count"]:
            post += '\n[details="Runner-ups"]\n'

            for i, entrant in enumerate(item["sorted_winner_list"]):
                if i >= item["winners_count"]:
                    post += generate_entry(i + 1, entrant, False)

            post += "[/details]\n"

        post += "\n"

    return post


def generate_post_data(all_items: list) -> str:
    post = (
        "*This post is generated by the rafflebot!"
        + " All code is open source, please see https://github.com/vhs/raffle"
        + " to see how this is generated,"
        + " and how you can verify the results at home.*\n\n"
    )

    post += "<h1>Data Dump</h1>\n\n"

    post += '[details="Base64 data"]\n`'
    post += base64.b64encode(gzip.compress(pickle.dumps(all_items))).decode()
    post += "`\n[/details]"

    return post


def generate_entry(idx: int, entrant: dict, tagged: bool) -> str:
    output = ""

    output += str(idx)
    output += ". "
    if tagged:
        output += "@"
    output += entrant["username"]
    output += " - "
    output += entrant["user-item-dice-result"].hex()[:8]
    output += "...\n"

    return output


class DiscourseConnection:
    def __init__(self, url, discourse_api_key, api_username="system") -> None:
        self._discource_client = DiscourseClient(
            url, api_username=api_username, api_key=discourse_api_key
        )

    def make_post(self, topic_id: int, post: str) -> None:
        self._discource_client.create_post(post, topic_id=topic_id)

    def get_all_voters(self, post_id, poll_name, option_id):
        results = []

        i = 1

        # Hacky way to get voters directly
        page = self._discource_client._request(
            "GET",
            "/polls/voters.json",
            params={
                "post_id": post_id,
                "poll_name": poll_name,
                "option_id": option_id,
                "page": i,
            },
        )["voters"][option_id]

        results += page

        i += 1

        while len(page) != 0:
            page = self._discource_client._request(
                "GET",
                "/polls/voters.json",
                params={
                    "post_id": post_id,
                    "poll_name": poll_name,
                    "option_id": option_id,
                    "page": i,
                },
            )["voters"][option_id]

            results += page

            i += 1

        # Ugh that (^^^) was a lame way of doing this, I was tired,
        # TODO: Make this cooler/cleaner for pagination and the actual request
        return results

    def get_all_polls(self, post_id: int, close_time_override: datetime = None) -> list:
        assert isinstance(post_id, int)

        topic = self._discource_client.topic_posts(str(post_id))

        all_poll_items = []

        for post in topic["post_stream"]["posts"]:
            if "polls" not in post:
                # Skip if this post doesn't have any polls in it
                # (most will skip, only a few polls per post)
                continue

            for poll in post["polls"]:
                for item in poll["options"]:
                    winnable_item = {}
                    winnable_item["description"] = item["html"]
                    winnable_item["id"] = item["id"]

                    if close_time_override:
                        winnable_item["close_time"] = int(
                            close_time_override.timestamp())
                    else:
                        try:
                            winnable_item["close_time"] = int(
                                datetime.fromisoformat(
                                    poll["close"].replace("Z", "+00:00")
                                ).timestamp()
                            )
                        except:
                            err(
                                "Problem with close time for poll."
                                + " Close time is used for hash generation"
                                + " and is needed. You can specify"
                                + " from command line if needed"
                            )
                            exit()

                    winnable_item["entrants"] = self.get_all_voters(
                        post["id"], poll["name"], item["id"]
                    )

                    all_poll_items.append(winnable_item)

        return all_poll_items
