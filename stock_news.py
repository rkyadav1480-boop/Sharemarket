import requests
from bs4 import BeautifulSoup

def google_news(stock):

    results = []

    try:

        query = (
            f"{stock} share market india"
        )

        url = (
            "https://www.google.com/search?q="
            f"{query}&tbm=nws"
        )

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64)"
            )
        }

        r = requests.get(
            url,
            headers=headers,
            timeout=20
        )

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        articles = soup.select("div.SoaBEf")

        print(
            "ARTICLES:",
            stock,
            len(articles)
        )

        if not articles:
            return results

        article = articles[0]

        title_tag = article.select_one(
            "div.MBeuO"
        )

        link_tag = article.find("a")

        source_tag = article.select_one(
            ".NUnG9d span"
        )

        time_tag = article.select_one(
            ".OSrXXb span"
        )

        title = (
            title_tag.get_text(strip=True)
            if title_tag else "No Title"
        )

        link = ""

        if link_tag:
            link = (
                "https://www.google.com"
                + link_tag.get("href")
            )

        source = (
            source_tag.get_text(strip=True)
            if source_tag else "Google News"
        )

        news_time = (
            time_tag.get_text(strip=True)
            if time_tag else ""
        )

        results.append({

            "source": source,

            "title": title,

            "url": link,

            "time": news_time
        })

    except Exception as e:

        print(
            "GOOGLE ERROR:",
            stock,
            e
        )

    return results