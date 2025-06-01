
from urllib.parse import urljoin
import re




def get_event_date_by_title(tree, title_text):
    for node in tree.css("dd[itemprop='events']"):
        title = node.css_first("span[itemprop='title']")
        date = node.css_first("time[itemprop='date']")
        if title and date and title.text(strip=True) == title_text:
            return date.attributes.get("datetime", "")
    return ""



# we got the title and date already when getting urls.
field_rules_article_basic = {
    "title": lambda tree: tree.css_first('meta[itemprop="headline"]').attributes.get("content", "") 
             if tree.css_first('meta[itemprop="headline"]') else "",
    "date": lambda tree: tree.css_first('meta[itemprop="datePublished"]').attributes.get("content", "") 
             if tree.css_first('meta[itemprop="datePublished"]') else "",
    "text": lambda tree: tree.css_first('[itemprop="text"]').text(strip=True) if tree.css_first('[itemprop="text"]') else "",
    
    "image": lambda tree: tree.css_first('meta[itemprop="image"]').attributes.get("content", "") 
             if tree.css_first('meta[itemprop="image"]') else ""  

    
}
field_rules_kawasaki = {
    "title": lambda tree: tree.css_first('h1').text(strip=True) 
             if tree.css_first('h1') else "",
             
    "date": lambda tree: tree.css_first('div.row.date p').text(strip=True) 
             if tree.css_first('div.row.date p') else "",
             
    "text": lambda tree: "\n\n".join(
        [p.text(strip=True) for p in tree.css('div#mainContentsArea p.pMargin_01') if p.text(strip=True)] +
        [li.text(strip=True) for li in tree.css('div#mainContentsArea ol.list_03 li') if li.text(strip=True)]
    ),
    

    "image": lambda tree: urljoin(
        "https://global.kawasaki.com",
        (tree.css_first('div.row.block img').attributes.get('src') or "")
        if tree.css_first('div.row.block img') else ""
    )

}


field_rules_wartsila = {

    "title": (
        lambda tree: (
            tree.css_first('div.hero-image__section h1').text(strip=True)
            if tree.css_first('div.hero-image__section h1') else ""
        )
    ),


    "date": (
        lambda tree: (
            tree.css_first('div.metadata__date span').text(strip=True)
            if tree.css_first('div.metadata__date span') else ""
        )
    ),

    "text": (
        lambda tree: "\n\n".join(
            [p.text(strip=True) for p in tree.css('div.main-body-wrapper p') if p.text(strip=True)] +
            [li.text(strip=True) for li in tree.css('div.main-body-wrapper li') if li.text(strip=True)]
        )
    ),

    "image": (
        lambda tree: urljoin(
            "https://www.wartsila.com",
            (
                (img := tree.css_first('div#content-wrapper img.responsive-image'))
                and (img.attributes.get('data-src') or img.attributes.get('src') or "")
            ) or ""
        )
    ),
}


field_rules_oedigital = {
    "title": lambda tree: (
        tree.css_first("title").text(strip=True) if tree.css_first("title") else ""
    ),
    "date": lambda tree: (
        tree.css_first('time[itemprop="datePublished"]').attributes.get("datetime", "")
        if tree.css_first('time[itemprop="datePublished"]') else ""
    ),
    "text": lambda tree: (
        tree.css_first('[property="articleBody"]').text(strip=True)
        if tree.css_first('[property="articleBody"]') else ""
    ),
    "image": lambda tree: (
        tree.css_first(".images-wrapper img").attributes.get("src", "")
        if tree.css_first(".images-wrapper img") else ""
    ),
}


field_rules_maritimeexec = {
    "title": (
        lambda tree: (
            tree.css_first('h1.article-title').text(strip=True)
            if tree.css_first('h1.article-title') else ""
        )
    ),
    "date": (
        lambda tree: (
            (lambda t: re.sub(r'\s+', ' ',              # collapse whitespace
                              re.sub(r'^(Published\s*)?|(\s*by.*$)', '', t)).strip()
            )(
                tree.css_first('p.datePublished').text()  # raw text
            )
            if tree.css_first('p.datePublished') else ""
        )
    ),
    "text": (
        lambda tree: "\n\n".join(
            [p.text(strip=True) for p in tree.css('#article-container p') if p.text(strip=True)] +
            [li.text(strip=True) for li in tree.css('#article-container li') if li.text(strip=True)]
        )
    ),

    "image": (
        lambda tree: urljoin(
            "https://maritime-executive.com",
            (
                (img := tree.css_first('figure.image img'))
                and (img.attributes.get('src') or "")
            ) or ""
        )
    ),
}


#### Rules for google patent extraction  domain 
field_rules_google_patent = {
    "title": lambda tree: (
        tree.css_first("title").text(strip=True).split(" - ")[1]
        if tree.css_first("title") and " - " in tree.css_first("title").text(strip=True)
        else ""
    ),
    "abstract": lambda tree: (
        " ".join([
            node.text(strip=True)
            for node in tree.css("section[itemprop='abstract'] div[itemprop='content'] .abstract")
        ])
        or (
            tree.css_first("section[itemprop='abstract'] div[itemprop='content']").text(strip=True)
            if tree.css_first("section[itemprop='abstract'] div[itemprop='content']") else ""
        )
    ),
    "claims": lambda tree: " ".join([
        node.text(strip=True)
        for node in tree.css("claim-text, div.claim-text")
    ]),
    "description": lambda tree: " ".join([
        node.text(strip=True)
        for node in tree.css("div[itemprop='content'] .description-paragraph")
    ]),

    "cited_by": lambda tree: [
        node.text(strip=True)
        for node in tree.css("tr[itemprop='forwardReferencesOrig'] span[itemprop='publicationNumber']")
    ],

    "citations": lambda tree: [
        node.text(strip=True)
        for node in tree.css("tr[itemprop='backwardReferencesOrig'] span[itemprop='publicationNumber']")
    ],

    "similar_documents": lambda tree: [
        node.text(strip=True)
        for node in tree.css("tr[itemprop='similarDocuments'] span[itemprop='publicationNumber']")
    ],

    # Dates from <time> tags
    "priority_date": lambda tree: (
        tree.css_first("time[itemprop='priorityDate']")
        .attributes.get("datetime", "")
        if tree.css_first("time[itemprop='priorityDate']") else ""
    ),
    "publication_date": lambda tree: (
        tree.css_first("time[itemprop='publicationDate']")
        .attributes.get("datetime", "")
        if tree.css_first("time[itemprop='publicationDate']") else ""
    ),

    # Dates from events by matching event title
    "application_granted": lambda tree: get_event_date_by_title(tree, "Application granted"),
    "approx_expiration": lambda tree: get_event_date_by_title(tree, "Anticipated expiration"),

    # Legal status
    "status": lambda tree: (
        tree.css_first("span[itemprop='status']")
        .text(strip=True)
        if tree.css_first("span[itemprop='status']") else ""
    )
}


DOMAIN_FIELD_RULES = {
    "patents.google.com": field_rules_google_patent,
    "www.marinelink.com": field_rules_article_basic,
    "www.oedigital.com":  field_rules_oedigital,
    "global.kawasaki.com": field_rules_kawasaki,
    "www.wartsila.com": field_rules_wartsila,
    "maritime-executive.com": field_rules_maritimeexec

    # Add more domains as needed
}

