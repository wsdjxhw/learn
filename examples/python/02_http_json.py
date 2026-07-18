import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def fetch_json(url: str) -> list[dict]:
    # Request a URL, read the response body, then parse JSON into Python data.
    with urlopen(url, timeout=10) as response:
        data = response.read().decode("utf-8")
        return json.loads(data)


def main() -> None:
    url = "https://jsonplaceholder.typicode.com/posts"

    try:
        posts = fetch_json(url)
    except HTTPError as exc:
        # The server responded, but the status code was not successful.
        print(f"HTTP error: {exc.code}")
        return
    except URLError as exc:
        # The request did not reach the server, for example network failure.
        print(f"Network error: {exc.reason}")
        return

    print(f"Total posts: {len(posts)}")

    # Print only the first 3 items so the output stays short.
    for post in posts[:3]:
        if post["userId"] != 1:
            continue
        print(f"[{post['id']}] {post['title']}")
        if(post["id"] == 1):
            print(f"    {post['body']}")


if __name__ == "__main__":
    main()
