import re

class ArticleMetadataProcessor:
    def __init__(self):
        """
        Defines keyword categories for focused metadata extraction.
        """
        self.kongsberg_keywords = [
            "kongsberg", "kongsberg gruppen", "kongsberg maritime",
            "kongsberg defence", "nasams", "remote weapon system", "jms", "joint strike missile"
        ]

        self.maritime_keywords =  [
            # General Maritime Operations
            "vessel", "ship", "shipping", "shipyard", "seafaring", "maritime",
            "offshore", "fleet", "dredging", "harbor", "port", "dry dock",

            # Engineering & Propulsion
            "hull", "propeller", "thruster", "rudder", "ballast", "anchor",
            "turbine", "diesel-electric", "dynamic positioning", "azimuth", "stern", "keel",

            # Navigation & Communication
            "radar", "sonar", "GPS", "AIS", "ECDIS", "bridge system", "radio beacon", "GNSS",

            # Environment & Energy
            "emissions", "scrubber", "ballast water treatment", "carbon capture",
            "green fuel", "methanol", "LNG", "hybrid propulsion",
            "marine pollution", "sustainability", "decarbonization",

            # Autonomy & Technology
            "autonomous ship", "unmanned vessel", "remote control", "digital twin",
            "smart shipping", "predictive maintenance", "condition monitoring",
            "control system", "maritime AI", "edge computing", "cyber security",

            # Safety & Regulation
            "SOLAS", "IMO", "lifesaving appliance", "lifeboat", "distress signal",
            "fire suppression", "collision avoidance", "maritime safety",
            "marine insurance", "regulatory compliance"
        ]

        self.kongsberg_patents_keywords = [
            "autonomous vessel",
            "dynamic positioning system",
            "remote weapon system",
            "fire control system",
            "combat system",
            "sonar system",
            "underwater vehicle",
            "unmanned surface vehicle",
            "unmanned underwater vehicle",
            "propulsion system",
            "thruster control",
            "maritime situational awareness",
            "missile guidance system",
            "target tracking system",
            "radar signal processing",
            "satellite navigation",
            "underwater sensor",
            "torpedo launch system",
            "vessel control system",
            "ballistic missile defense",
            "stealth technology",
            "electronic warfare",
            "multibeam sonar",
            "real-time positioning",
            "autonomous navigation",
            "AI ship control",
            "bridge automation",
            "marine surveillance",
            "military communications",
            "anti-submarine warfare"
            ]
        
        self.maritime_patent_keywords = [
            # Vessel and Hull Technologies
            "ship hull", "composite hull", "hull cleaning", "anti-fouling coating",
            "double hull", "ballast system", "ship design",

            # Propulsion and Power Systems
            "azimuth thruster", "propulsion system", "electric propulsion", "hybrid propulsion",
            "diesel-electric", "turbine propulsion", "marine engine", "waterjet propulsion",

            # Navigation and Control
            "autonomous vessel", "autonomous navigation", "dynamic positioning",
            "control system", "course correction", "collision avoidance",
            "marine radar", "sonar system", "gyrocompass", "navigation algorithm",

            # Energy and Sustainability
            "methanol fuel", "LNG propulsion", "hydrogen fuel cell", "carbon capture",
            "emissions control", "waste heat recovery", "green ship technology",

            # Communications and Sensors
            "maritime communication", "satellite tracking", "vessel monitoring system",
            "condition monitoring", "predictive maintenance", "marine sensor",

            # Safety and Compliance
            "lifesaving equipment", "fire suppression system", "oil spill detection",
            "emergency evacuation system", "IMO compliance", "SOLAS equipment",

            # Subsea and Offshore
            "ROV", "AUV", "subsea cable", "offshore platform", "drilling riser",
            "subsea pipeline", "anchor system", "mooring system",

            # Advanced Software and Autonomy
            "digital twin", "marine simulation", "route optimization",
            "AI for maritime", "autonomous docking", "machine learning navigation"
        ]
    def extract_matches(self, text, keyword_list):
        if not text:
            return []

        text_lower = text.lower()
        matched = {
            kw.lower() for kw in keyword_list
            if re.search(rf"\b{re.escape(kw.lower())}\b", text_lower)
        }

        return sorted(matched)

    def enrich_dataframe(self, df, domain):
        """
        Adds 'keywords_kongsberg' and 'keywords_maritime' columns to the DataFrame.
        """
        df = df.copy()
        if domain == "news":
            df["keywords_kongsberg"] = df["text"].apply(lambda x: self.extract_matches(x, self.kongsberg_keywords))
            df["keywords_maritime"] = df["text"].apply(lambda x: self.extract_matches(x, self.maritime_keywords))
        elif domain == "patents":
            def extract_from_patent(row, keyword_list):
                parts = [row.get("description", ""), row.get("abstract", ""), row.get("claims", "")]
                combined_text = " ".join(filter(None, parts))
                return self.extract_matches(combined_text, keyword_list)
            df["keywords_kongsberg"] = df.apply(lambda row: extract_from_patent(row, self.kongsberg_patents_keywords), axis=1)
            df["keywords_maritime"] = df.apply(lambda row: extract_from_patent(row, self.maritime_patent_keywords), axis=1)

        return df