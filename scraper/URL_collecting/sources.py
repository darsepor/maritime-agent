field_rules_wartsila = {
    "articles": lambda tree: [
        {
            "headline": card.css_first("figcaption .h4").text(strip=True),
            "date": card.css_first("span.pr-4").text(strip=True) if card.css_first("span.pr-4") else None,
            "url": card.css_first("a.anchor-reset").attributes.get("href", "").strip()
        }
        for card in tree.css("div.card-lift")
        if card.css_first("figcaption .h4") and card.css_first("a.anchor-reset")
    ]
}


field_rules_kawasaki = {
    "articles": lambda tree: [
        {
            "headline": a.text(strip=True),
            "date": dl.css_first("dt span").text(strip=True) if dl.css_first("dt span") else None,
            "url": "https://global.kawasaki.com" + a.attributes.get("href", "").strip()
        }
        for dl in tree.css("dl.line_1ofList")
        if (a := dl.css_first("dd a"))
    ]
}


field_rules_oedigital = {
    "articles": lambda tree: [
        {
            "headline": a.css_first("h2").text(strip=True),
            "date": a.css_first("div.meta").text(strip=True) if a.css_first("div.meta") else None,
            "url": "https://www.oedigital.com" + a.attributes.get("href", "").strip()
        }
        for a in tree.css("a.snippet")
        if a.css_first("h2")
    ]
}




wartsila_urls = {"url_base":"https://www.wartsila.com/insights/business-areas/marine/articles",
                 "categories": None,
                "page_logic": None,  # the parameter key
                "articles_per_page": None,
                "field_rules": field_rules_wartsila
                }



kawasaki_urls = {"url_base": "https://global.kawasaki.com/en/corp/newsroom/news/index.html?year=&category=6",
                 "categories": None,
                "page_logic": None,  # the parameter key
                "articles_per_page": None,
                 "field_rules": field_rules_kawasaki
                  }

oedigital_urls = {"url_base": "https://www.oedigital.com/",
                 "categories": ["marine-propulsion", "vessels", "subsea"],
                "page_logic": "start",  # the parameter key
                "articles_per_page": 15,
                 "field_rules": field_rules_oedigital
                  }




   
DOMAIN_RULES_URL = {
    "www.wartsila.com": wartsila_urls,
    "global.kawasaki.com": kawasaki_urls,
    "www.oedigital.com":  oedigital_urls,
    
}


domains = ["www.wartsila.com", "global.kawasaki.com", "www.oedigital.com"]
