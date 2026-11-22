"""Rule-based understanding of citizen messages in en / hi / kn / ta / Hinglish.

Used (a) as the whole classifier when MOCK_LLM=true or the LLM fails, and (b) always, as a
guard next to the LLM: safety signals (fraud, bribe, another person's data, injection) are
decided here in code, and LLM-extracted numbers are accepted only if they appear in the
message text."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

INDIC_DIGITS = str.maketrans("०१२३४५६७८९೦೧೨೩೪೫೬೭೮೯௦௧௨௩௪௫௬௭௮௯", "0123456789" * 3)


def norm(text: str) -> str:
    return (text or "").translate(INDIC_DIGITS)


def _has(text: str, words: list[str]) -> bool:
    """Latin words match on word boundaries; Indic words match as substrings (they inflect)."""
    low = text.lower()
    for w in words:
        if re.search(r"[a-z]", w):
            if re.search(rf"(?<![a-z]){re.escape(w)}(?![a-z])", low):
                return True
        elif w in text:
            return True
    return False


# ------------------------------------------------------------------ lexicons
RELATION_FEMALE = ["mother", "mom", "mummy", "maa", "amma", "mataji", "wife", "patni", "beti", "daughter",
                   "sister", "behen", "behan", "dadi", "nani", "grandmother", "bahu", "thaayi", "thayi", "ammavukku",
                   "माँ", "मां", "माता", "मम्मी", "पत्नी", "बेटी", "बहन", "दादी", "नानी", "बहू",
                   "ತಾಯಿ", "ಅಮ್ಮ", "ಹೆಂಡತಿ", "ಮಗಳು", "ಅಕ್ಕ", "ತಂಗಿ", "ಅಜ್ಜಿ",
                   "அம்மா", "தாய்", "மனைவி", "மகள்", "அக்கா", "தங்கை", "பாட்டி"]
RELATION_MALE = ["father", "dad", "papa", "pitaji", "husband", "pati", "son", "beta", "brother", "bhai", "dada",
                 "nana", "grandfather", "appa", "thande",
                 "पिता", "पिताजी", "पापा", "पति", "बेटा", "भाई", "दादा", "नाना",
                 "ತಂದೆ", "ಅಪ್ಪ", "ಗಂಡ", "ಮಗ ", "ಅಣ್ಣ", "ತಮ್ಮ", "ಅಜ್ಜ",
                 "அப்பா", "தந்தை", "கணவர்", "மகன்", "அண்ணன்", "தம்பி", "தாத்தா"]
SELF_FEMALE = ["i am a woman", "i am female", "mahila", "ladki", "girl", "widow", "vidhwa", "female",
               "महिला", "लड़की", "विधवा", "ಮಹಿಳೆ", "ಹುಡುಗಿ", "பெண்", "சிறுமி"]
SELF_MALE = ["i am a man", "male", "purush", "ladka", "boy", "पुरुष", "लड़का", "ಪುರುಷ", "ಹುಡುಗ", "ஆண்"]

OCCUPATIONS: dict[str, list[str]] = {
    "farmer": ["farmer", "farming", "farm", "kisan", "kisaan", "kheti", "khet", "agriculture", "tenant farmer",
               "raitha", "raita", "vivasayi", "vivasayam",
               "किसान", "खेती", "कृषक", "ರೈತ", "ಕೃಷಿ", "ವ್ಯವಸಾಯ", "விவசாயி", "விவசாயம்"],
    "student": ["student", "studying", "studies", "padhai", "padhti", "padhta", "college", "school", "class 9",
                "class 10", "class 11", "class 12", "graduation",
                "छात्र", "छात्रा", "विद्यार्थी", "पढ़ती", "पढ़ता", "पढ़ाई", "कॉलेज", "स्कूल",
                "ವಿದ್ಯಾರ್ಥಿ", "ಓದುತ್ತಿ", "ಕಾಲೇಜು", "ಶಾಲೆ", "மாணவர்", "மாணவி", "படிக்கிற", "கல்லூரி", "பள்ளி"],
    "daily_wage": ["daily wage", "daily-wage", "labourer", "laborer", "labour", "mazdoor", "majdoor", "mazdoori",
                   "dihadi", "coolie", "मज़दूर", "मजदूर", "दिहाड़ी", "मजदूरी", "ಕೂಲಿ", "கூலி"],
    "construction_worker": ["construction", "mason", "mistri", "निर्माण", "राजमिस्त्री", "ಕಟ್ಟಡ ಕಾರ್ಮಿಕ", "கட்டுமான"],
    "street_vendor": ["street vendor", "vendor", "hawker", "thela", "rehri", "ठेला", "रेहड़ी", "फेरीवाला",
                      "ಬೀದಿ ವ್ಯಾಪಾರ", "தெரு வியாபார"],
    "homemaker": ["homemaker", "housewife", "grihini", "गृहिणी", "ಗೃಹಿಣಿ", "இல்லத்தரசி"],
    "retired": ["retired", "pensioner", "सेवानिवृत्त", "रिटायर", "ನಿವೃತ್ತ", "ஓய்வு பெற்ற"],
    "unemployed": ["unemployed", "berozgar", "no job", "बेरोज़गार", "बेरोजगार", "ನಿರುದ್ಯೋಗಿ", "வேலையில்லா"],
    "salaried": ["salaried", "government job", "private job", "naukri", "नौकरी", "ಸಂಬಳ", "சம்பளம்"],
}
RURAL = ["village", "rural", "gaon", "gaanv", "gav", "gram", "गाँव", "गांव", "ग्रामीण", "ಹಳ್ಳಿ", "ಗ್ರಾಮ", "கிராமம்", "கிராமத்தில்"]
URBAN = ["city", "town", "urban", "shahar", "nagar", "शहर", "नगर", "शहरी", "ನಗರ", "ಪಟ್ಟಣ", "நகரம்", "நகரத்தில்", "டவுன்"]
DISTRICTS = {"Nayagaon": ["nayagaon", "nayagaun", "नयागाँव", "नयागांव", "ನಯಾಗಾಂವ್", "நயாகாவ்"],
             "Sundarpur": ["sundarpur", "सुंदरपुर", "सुन्दरपुर", "ಸುಂದರಪುರ", "சுந்தர்பூர்"],
             "Kaverinadu": ["kaverinadu", "कावेरीनाडु", "ಕಾವೇರಿನಾಡು", "காவேரிநாடு"],
             "Thenpuram": ["thenpuram", "तेनपुरम", "ತೆನ್ಪುರಂ", "தென்புரம்"]}
CATEGORY = {"sc": ["sc", "scheduled caste", "dalit", "anusuchit jati", "अनुसूचित जाति", "ಪರಿಶಿಷ್ಟ ಜಾತಿ", "பட்டியல் சாதி", "ஆதிதிராவிடர்"],
            "st": ["st", "scheduled tribe", "adivasi", "anusuchit janjati", "अनुसूचित जनजाति", "आदिवासी", "ಪರಿಶಿಷ್ಟ ಪಂಗಡ", "பழங்குடி"],
            "obc": ["obc", "backward class", "pichhda varg", "पिछड़ा वर्ग", "ಹಿಂದುಳಿದ ವರ್ಗ", "பிற்படுத்தப்பட்ட"],
            "general": ["general category", "samanya", "सामान्य वर्ग", "ಸಾಮಾನ್ಯ ವರ್ಗ", "பொதுப் பிரிவு"]}
DISABILITY = ["disabled", "disability", "handicapped", "viklang", "divyang", "विकलांग", "दिव्यांग", "ಅಂಗವಿಕಲ",
              "ವಿಕಲಚೇತನ", "ದಿವ್ಯಾಂಗ", "ಅಂಗವೈಕಲ್ಯ", "மாற்றுத்திறனாளி", "மாற்றுத்திறன்", "ஊனமுற்ற"]
NOT_DISABLED = ["not disabled", "no disability", "विकलांग नहीं", "दिव्यांग नहीं", "ಅಂಗವೈಕಲ್ಯ ಇಲ್ಲ", "மாற்றுத்திறனாளி இல்லை"]
YES = ["yes", "haan", "ha", "han", "ji haan", "हाँ", "हां", "ಹೌದು", "ஆம்", "aamam", "howdu"]
NO = ["no", "nahi", "nahin", "नहीं", "ನಹಿ", "ಇಲ್ಲ", "இல்லை", "illa", "illai"]

INCOME_WORDS = ["income", "earn", "earning", "salary", "aay", "aamdani", "amdani", "kamai", "kamate", "kamata",
                "varumanam", "varumaanam", "sambalam", "aadaya", "adaya",
                "आय", "आमदनी", "कमाई", "ಆದಾಯ", "ಸಂಪಾದ", "வருமானம்", "வருமான", "சம்பாத்"]
MONTHLY = ["per month", "a month", "monthly", "mahina", "mahine", "maheena", "प्रति माह", "महीने", "मासिक",
           "ತಿಂಗಳ", "ತಿಂಗಳಿಗೆ", "மாதம்", "மாதத்திற்கு"]
AGE_UNITS = r"(?:years?|yrs?|yr|saal|sal|baras|varsh|वर्ष|साल|बरस|ವರ್ಷ|வயது|vayasu|vayassu)"
AGE_WORDS = r"(?:age|aged|umar|umra|vayasu|vayassu|vayasa|उम्र|आयु|ವಯಸ್ಸು|வயது)"
LAKH = r"(?:lakh|lakhs|lac|laakh|लाख|ಲಕ್ಷ|லட்சம்|லட்ச)"
THOUSAND = r"(?:thousand|hazaar|hazar|हज़ार|हजार|ಸಾವಿರ|ஆயிரம்|k)\b"

# ------------------------------------------------------------------ intent lexicons
FRAUD = ["release my scheme money", "release fee", "release the money", "processing fee", "registration fee",
         "pay ₹", "pay rs", "must pay", "asked me to pay", "asking for otp", "asked for otp", "share otp",
         "share my otp", "otp maang", "otp mang", "otp batao", "otp do", "bank details", "account details",
         "someone called", "a man says", "a man called", "agent says", "agent is asking", "call aaya", "phone aaya",
         "lottery", "kyc update", "पैसे जमा", "फीस मांग", "ओटीपी मांग", "OTP मांग", "OTP बता", "बैंक डिटेल", "कॉल आया",
         "ಹಣ ಕಟ್ಟ", "OTP ಕೇಳ", "ಒಟಿಪಿ ಕೇಳ", "ಕರೆ ಮಾಡಿ", "பணம் கட்ட", "OTP கேட்", "ஓடிபி கேட்", "அழைத்து"]
BRIBE = ["bribe", "rishwat", "ghoos", "ghus", "paise maang", "paise mang", "money for", "asking for money",
         "asked for money", "demanding money", "officer paise", "babu paise", "chai pani", "रिश्वत", "घूस",
         "पैसे मांग", "पैसे माँग", "ಲಂಚ", "ಹಣ ಕೇಳುತ್ತಿದ್ದಾರೆ", "லஞ்சம்", "பணம் கேட்கிறார்"]
REJECTION = ["rejected", "rejection", "reject ho", "reject kar", "asvikar", "अस्वीकार", "रिजेक्ट", "नामंजूर",
             "ತಿರಸ್ಕರಿ", "ತಿರಸ್ಕೃತ", "நிராகரி"]
DELAY = ["not received", "not credited", "no payment", "still pending", "pending for", "delay", "delayed", "deri",
         "nahi aaya", "nahi aayi", "abhi tak nahi", "नहीं आया", "नहीं आई", "देरी", "अभी तक नहीं", "ವಿಳಂಬ",
         "ಬಂದಿಲ್ಲ", "தாமதம்", "வரவில்லை"]
HUMAN = ["human", "real person", "officer se baat", "adhikari se baat", "bade adhikari", "senior officer",
         "talk to an officer", "speak to an officer", "talk to someone", "speak to a person", "insaan se",
         "complaint", "shikayat", "अधिकारी से बात", "बड़े अधिकारी", "शिकायत", "ಅಧಿಕಾರಿಯೊಂದಿಗೆ", "ಅಧಿಕಾರಿ ಜೊತೆ",
         "ದೂರು", "அதிகாரியிடம்", "அலுவலரிடம்", "புகார்"]
REPEATED = ["third time", "3rd time", "teesri baar", "tisri baar", "fourth time", "again and again", "baar baar",
            "many times", "kitni baar", "तीसरी बार", "बार बार", "बार-बार", "कई बार", "ಮೂರನೇ ಬಾರಿ", "ಮತ್ತೆ ಮತ್ತೆ",
            "மூன்றாவது முறை", "பல முறை"]
FRUSTRATION = ["fed up", "frustrated", "pareshan", "tang aa", "angry", "useless", "परेशान", "तंग आ", "ಬೇಸರ",
               "ಸಾಕಾಗಿದೆ", "வெறுப்பு", "சலிப்பு", "!!"]
DISTRESS = ["no food", "starving", "hospital", "emergency", "suicide", "dying", "भूखे", "अस्पताल", "ಆಸ್ಪತ್ರೆ", "மருத்துவமனை"]
LEGAL = ["lawyer", "court", "legal notice", "sue", "vakil", "वकील", "कोर्ट", "ವಕೀಲ", "ನ್ಯಾಯಾಲಯ", "வழக்கறிஞர்", "நீதிமன்ற"]
OUT_OF_SCOPE = ["election", "chunav", "vote", "cricket", "movie", "film", "weather", "joke", "recipe", "stock market",
                "share market", "bitcoin", "politics", "prime minister", "who will win", "चुनाव", "क्रिकेट", "फिल्म",
                "मौसम", "ಚುನಾವಣೆ", "ಕ್ರಿಕೆಟ್", "ಸಿನಿಮಾ", "தேர்தல்", "கிரிக்கெட்", "திரைப்படம்", "வானிலை"]
SECRET = ["system prompt", "your prompt", "your instructions", "api key", "password", "database dump",
          "show me the rules you follow", "internal instructions"]
OTHER_PERSON = ["neighbour", "neighbor", "padosi", "someone else's", "another person", "other person", "his income",
                "her income", "पड़ोसी", "ಪಕ್ಕದ ಮನೆ", "ನೆರೆಹೊರೆ", "பக்கத்து வீட்டு", "அண்டை வீட்டு"]
BOOK = ["book", "booking", "slot", "appointment", "visit", "milne", "samay lena", "बुक", "अपॉइंटमेंट", "मुलाकात",
        "ಬುಕ್", "ಭೇಟಿ", "ಅಪಾಯಿಂಟ್", "முன்பதிவு", "சந்திப்பு", "அப்பாயிண்ட்"]
CENTRE = ["centre", "center", "kendra", "office", "seva", "केंद्र", "केन्द्र", "दफ्तर", "ಕೇಂದ್ರ", "ಕಚೇರಿ", "மையம்", "அலுவலகம்"]
CANCEL = ["cancel", "radd", "रद्द", "कैंसल", "ರದ್ದು", "ರದ್ದುಮಾಡ", "ரத்து"]
REMIND = ["remind", "reminder", "yaad dila", "याद दिला", "रिमाइंडर", "ನೆನಪಿಸ", "ಜ್ಞಾಪನೆ", "நினைவூட்ட", "நினைவு படுத்த"]
DRAFT = ["fill in the", "fill the form", "fill my form", "fill form", "fill in my", "draft", "prepare my application",
         "prepare the application", "apply for me", "form bhar", "form bharo", "aavedan bhar", "फॉर्म भर", "फ़ॉर्म भर",
         "आवेदन भर", "आवेदन तैयार", "ಅರ್ಜಿ ತುಂಬ", "ಫಾರ್ಮ್ ತುಂಬ", "விண்ணப்பம் நிரப்ப", "படிவம் நிரப்ப", "விண்ணப்பத்தை நிரப்ப"]
DOCUMENTS = ["document", "documents", "docs", "papers", "kagaz", "kaagaz", "kagzat", "kaagzaat", "dastavez",
             "certificate", "what do i need", "what is needed", "kya chahiye", "kya lagega", "lagenge", "दस्तावेज़",
             "दस्तावेज", "कागज", "काग़ज़", "कागजात", "प्रमाण पत्र", "ದಾಖಲೆ", "ದಾಖಲಾತಿ", "ಪ್ರಮಾಣಪತ್ರ", "ஆவணம்",
             "ஆவணங்கள்", "சான்றிதழ்", "accepted", "is valid", "maanya", "chalega", "मान्य", "चलेगा", "ಮಾನ್ಯ", "செல்லுமா", "ஏற்கப்படுமா"]
HOW_APPLY = ["how to apply", "how do i apply", "how can i apply", "kaise apply", "aavedan kaise", "kaise kare",
             "आवेदन कैसे", "ಹೇಗೆ ಅರ್ಜಿ", "ಅರ್ಜಿ ಸಲ್ಲಿಸುವುದು ಹೇಗೆ", "எப்படி விண்ணப்பி"]
DEADLINE = ["last date", "deadline", "still open", "is it open", "open hai", "kab tak", "closing date", "closed",
            "till when", "antim tithi", "aakhri tareekh", "akhri tarikh", "अंतिम तिथि", "आखिरी तारीख", "अंतिम तारीख",
            "कब तक", "ಕೊನೆಯ ದಿನಾಂಕ", "ಕೊನೆ ದಿನ", "ಯಾವಾಗವರೆಗೆ", "கடைசி தேதி", "கடைசி நாள்", "எப்போது வரை"]
APP_STATUS = ["application status", "status of my application", "my application", "mera aavedan", "mera application",
              "मेरा आवेदन", "आवेदन की स्थिति", "ನನ್ನ ಅರ್ಜಿ", "ಅರ್ಜಿಯ ಸ್ಥಿತಿ", "என் விண்ணப்ப", "விண்ணப்ப நிலை"]
ELIGIBILITY = ["eligible", "eligibility", "qualify", "can i apply", "can i still apply", "can we apply",
               "can she apply", "can he apply", "still apply", "apply kar sakta", "apply kar sakti", "can she get", "can he get", "can i get", "will i get",
               "will she get", "can we get", "milegi", "milega", "mil sakti", "mil sakta", "paatra", "patra",
               "पात्र", "मिलेगी", "मिलेगा", "मिल सकती", "मिल सकता", "ಸಿಗಬಹುದೇ", "ಸಿಗುತ್ತದೆಯೇ", "ಅರ್ಹ",
               "கிடைக்குமா", "தகுதி", "kidaikuma", "sigabahude"]
DISCOVERY = ["which schemes", "what schemes", "which scheme", "any scheme", "schemes for me", "kaun si yojana",
             "kaunsi yojana", "kon si yojana", "kya yojana", "कौन सी योजना", "कौन-सी योजना", "कौनसी योजना",
             "कौन सी योजनाएँ", "कौन सी योजनाएं", "ಯಾವ ಯೋಜನೆ", "ಯಾವ ಯೋಜನೆಗಳು", "என்ன திட்டங்கள்", "எந்தத் திட்ட",
             "எந்த திட்ட", "என்ன திட்டம்"]
SCHEME_INFO = ["what is", "tell me about", "about the", "details of", "details about", "benefit", "how much",
               "kya hai", "kya milta", "kitna milta", "kitna milega", "batao", "बारे में", "क्या है", "लाभ", "कितना मिलता",
               "ಬಗ್ಗೆ", "ಏನು", "ಎಷ್ಟು", "பற்றி", "என்ன", "எவ்வளவு"]
SELF_MARKERS = ["i am", "i'm", "my age", "for me", "for myself", "main ", "mera ", "meri umar", "मैं", "मेरी उम्र", "मेरा",
                "ನಾನು", "ನನಗೆ", "நான்", "எனக்கு", "naan ", "enakku"]
GREETING = ["hi", "hello", "namaste", "namaskar", "vanakkam", "namaskara", "नमस्ते", "नमस्कार", "ನಮಸ್ಕಾರ", "வணக்கம்"]
CONFIRM_WORDS = ["yes confirm", "confirm", "go ahead", "book it", "haan kar do", "kar do", "हाँ कर दो", "पुष्टि",
                 "ದೃಢೀಕರಿಸ", "உறுதிப்படுத்து", "ok do it"]
SCHEME_WORDS = ["scheme", "yojana", "yojna", "loan", "subsidy", "grant", "allowance", "benefit", "योजना", "ऋण",
                "लोन", "ಯೋಜನೆ", "ಸಾಲ", "திட்டம்", "கடன்", "மானியம்"]

# scheme keyword aliases (scheme names in all scripts are added from the DB at runtime)
SCHEME_ALIASES: dict[str, list[str]] = {
    "SCH-PEN-01": ["old age pension", "old-age pension", "old age", "vriddh", "vridh", "vriddhjan", "budhapa",
                   "बुढ़ापा", "वृद्ध", "वृद्धावस्था", "ವೃದ್ಧಾಪ್ಯ", "ವೃದ್ಧ", "முதியோர்", "pension", "पेंशन", "पेन्शन",
                   "ಪಿಂಚಣಿ", "ஓய்வூதிய"],
    "SCH-SCH-01": ["kanya", "girls scholarship", "girls' scholarship", "girl's scholarship", "girl student",
                   "scholarship for girls", "beti scholarship", "कन्या", "छात्राओं", "ಕನ್ಯಾ", "ವಿದ್ಯಾರ್ಥಿನಿ", "கன்யா", "மாணவிகள்"],
    "SCH-SCH-02": ["medhavi", "merit scholarship", "merit award", "class 12 award", "मेधावी", "ಮೇಧಾವಿ", "மேதாவி"],
    "SCH-FRM-01": ["kisan samriddhi", "samriddhi", "kisan scheme", "farmer support", "किसान समृद्धि", "ಕಿಸಾನ್", "கிசான்"],
    "SCH-FRM-02": ["krishi yantra", "farm machinery", "tractor subsidy", "machinery subsidy", "कृषि यंत्र", "ಕೃಷಿ ಯಂತ್ರ", "இயந்திர மானிய"],
    "SCH-HSG-01": ["grameen awas", "rural housing", "awas", "house grant", "ghar banane", "pucca house", "आवास",
                   "ग्रामीण आवास", "ಆವಾಸ", "ವಸತಿ", "வீட்டு உதவி", "வீடு கட்ட"],
    "SCH-HSG-02": ["shahari kiraya", "rent support", "rent help", "kiraya", "किराया", "ಬಾಡಿಗೆ", "வாடகை"],
    "SCH-DIS-01": ["divyang sambal", "disability pension", "disability support", "divyang", "दिव्यांग संबल",
                   "ದಿವ್ಯಾಂಗ", "திவ்யாங்", "மாற்றுத்திறனாளி உதவி"],
    "SCH-INS-01": ["suraksha bima", "insurance", "accident cover", "bima", "बीमा", "ಸುರಕ್ಷಾ", "ವಿಮೆ", "ವಿಮಾ",
                   "காப்பீடு", "சுரக்ஷா"],
}
BENEFIT_TYPE_WORDS: dict[str, list[str]] = {
    "scholarship": ["scholarship", "chhatravritti", "छात्रवृत्ति", "ವಿದ್ಯಾರ್ಥಿವೇತನ", "கல்வி உதவித்தொகை"],
    "housing": ["housing", "house", "ghar", "makaan", "मकान", "घर", "ಮನೆ", "வீடு"],
    "farmer_support": ["farmer scheme", "for farmers", "kisan yojana", "किसान योजना", "ರೈತ ಯೋಜನೆ", "விவசாயி திட்ட"],
}


# ------------------------------------------------------------------ numbers
def _num(s: str) -> float:
    return float(s.replace(",", ""))


def extract_income(text: str, expecting: bool = False) -> int | None:
    t = norm(text)
    has_word = _has(t, INCOME_WORDS)
    monthly = _has(t, MONTHLY)
    patterns = [
        (rf"(\d+(?:\.\d+)?)\s*{LAKH}", 100000),
        (rf"(\d+(?:\.\d+)?)\s*{THOUSAND}", 1000),
        (r"(?:₹|rs\.?|inr|rupees?)\s*(\d{1,3}(?:,\d{2,3})+|\d{4,})", 1),
        (r"(\d{1,3}(?:,\d{2,3})+|\d{5,7})\s*(?:₹|rs|rupees?|रुपये|रुपए|ರೂಪಾಯಿ|ரூபாய்)", 1),
    ]
    if not (has_word or expecting):
        return None
    for pat, mult in patterns:
        for m in re.finditer(pat, t, re.I):
            # skip amounts that are clearly fees/payments, not income
            ctx = t[max(0, m.start() - 25): m.start()].lower()
            if re.search(r"pay|fee|fees|charge|bribe|दे|फीस", ctx) and not has_word:
                continue
            val = _num(m.group(1)) * mult
            if monthly and val < 100000:
                val *= 12
            if 0 <= val < 1e9:
                return int(round(val))
    if expecting or has_word:
        m = re.search(r"(?<![\d.])(\d{1,3}(?:,\d{2,3})+|\d{4,7})(?![\d.])", t)
        if m:
            val = _num(m.group(1))
            return int(val * 12 if monthly and val < 100000 else val)
    return None


def extract_age(text: str, expecting: bool = False) -> int | None:
    t = norm(text)
    for pat in [rf"(\d{{1,3}})\s*-?\s*{AGE_UNITS}", rf"{AGE_WORDS}\D{{0,12}}(\d{{1,3}})",
                r"\b(?:is|hai|hain|he)\s+(\d{2,3})\b", r"\b(?:i am|i'm|im|she is|he is|main)\s+(\d{1,3})\b"]:
        m = re.search(pat, t, re.I)
        if m:
            v = int(m.group(1))
            if 0 < v <= 120:
                return v
    if expecting:
        for m in re.finditer(r"(?<![\d.,₹])(\d{1,3})(?![\d.,%])", t):
            v = int(m.group(1))
            if 0 < v <= 120:
                return v
    return None


def extract_land(text: str, expecting: bool = False) -> float | None:
    t = norm(text)
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:acres?|acre|ekad|ekar|एकड़|एकड|ಎಕರೆ|ஏக்கர்)", t, re.I)
    if m:
        return float(m.group(1))
    if re.search(r"no land|zameen nahi|ज़मीन नहीं|जमीन नहीं|ಜಮೀನು ಇಲ್ಲ|நிலம் இல்லை|landless", t, re.I):
        return 0.0
    if expecting:
        m = re.search(r"(?<![\d.,₹])(\d+(?:\.\d+)?)(?![\d,%])", t)
        if m and float(m.group(1)) < 1000:
            return float(m.group(1))
    return None


def extract_attributes(text: str, expecting: list[str] | None = None) -> tuple[dict[str, Any], str, str | None]:
    """Return (attributes, subject 'self'|'other', relation word). `expecting` lists the
    attributes we asked for last turn, which lets bare answers like "70" or "haan" count."""
    expecting = expecting or []
    t = norm(text)
    attrs: dict[str, Any] = {}
    relation = None
    female_rel = _has(t, RELATION_FEMALE)
    male_rel = _has(t, RELATION_MALE)
    subject = "other" if (female_rel or male_rel) else "self"
    if female_rel and not male_rel:
        attrs["gender"], relation = "female", "female_relative"
    elif male_rel and not female_rel:
        attrs["gender"], relation = "male", "male_relative"
    elif _has(t, SELF_FEMALE):
        attrs["gender"] = "female"
    elif _has(t, SELF_MALE):
        attrs["gender"] = "male"
    if "gender" in expecting and "gender" not in attrs:
        if re.search(r"\b(f|woman|lady)\b", t, re.I):
            attrs["gender"] = "female"
        elif re.search(r"\b(m|man)\b", t, re.I):
            attrs["gender"] = "male"

    inc = extract_income(t, expecting="annual_household_income" in expecting)
    if inc is not None:
        attrs["annual_household_income"] = inc
    t_wo_income = re.sub(rf"(\d+(?:\.\d+)?)\s*{LAKH}|(?:₹|rs\.?)\s*[\d,]+|[\d,]{{5,}}", " ", t, flags=re.I)
    land = extract_land(t_wo_income, expecting="land_holding_acres" in expecting and "age" not in expecting)
    if land is not None:
        attrs["land_holding_acres"] = land
    t_wo_land = re.sub(r"\d+(?:\.\d+)?\s*(?:acres?|acre|ekad|एकड़|एकड|ಎಕರೆ|ஏக்கர்)", " ", t_wo_income, flags=re.I)
    t_wo_land = re.sub(r"\d{1,3}\s*%", " ", t_wo_land)
    age = extract_age(t_wo_land, expecting="age" in expecting)
    if age is not None:
        attrs["age"] = age

    for occ, words in OCCUPATIONS.items():
        if _has(t, words):
            attrs["occupation"] = occ
            break
    if _has(t, RURAL):
        attrs["residence_type"] = "rural"
    elif _has(t, URBAN):
        attrs["residence_type"] = "urban"
    for d, words in DISTRICTS.items():
        if _has(t, words):
            attrs["district"] = d
            break
    for cat, words in CATEGORY.items():
        if _has(t, words):
            attrs["category"] = cat
            break
    if _has(t, NOT_DISABLED):
        attrs["is_disabled"] = "N"
    elif _has(t, DISABILITY):
        attrs["is_disabled"] = "Y"
        m = re.search(r"(\d{1,3})\s*(?:%|percent|pratishat|प्रतिशत|ಶೇಕಡಾ|சதவீத)", t, re.I)
        if m and int(m.group(1)) <= 100:
            attrs["disability_percent"] = int(m.group(1))
    if "disability_percent" in expecting and "disability_percent" not in attrs:
        m = re.search(r"(\d{1,3})\s*(?:%|percent)?", t)
        if m and int(m.group(1)) <= 100:
            attrs["disability_percent"] = int(m.group(1))
    if "is_disabled" in expecting and "is_disabled" not in attrs:
        if _has(t, YES):
            attrs["is_disabled"] = "Y"
        elif _has(t, NO):
            attrs["is_disabled"] = "N"
    if "category" in expecting and "category" not in attrs and _has(t, NO):
        attrs["category"] = "general"
    return attrs, subject, relation


def numbers_in(text: str) -> set[float]:
    """All numbers in a text, normalised (lakh expanded), used to verify LLM extractions."""
    t = norm(text)
    out: set[float] = set()
    for m in re.finditer(rf"(\d+(?:\.\d+)?)\s*{LAKH}", t, re.I):
        out.add(round(_num(m.group(1)) * 100000))
    for m in re.finditer(rf"(\d+(?:\.\d+)?)\s*{THOUSAND}", t, re.I):
        out.add(round(_num(m.group(1)) * 1000))
    for m in re.finditer(r"\d{1,3}(?:,\d{2,3})+|\d+(?:\.\d+)?", t):
        v = _num(m.group(0))
        out.add(v)
        out.add(v * 12)
    return out


# ------------------------------------------------------------------ schemes
def mentioned_schemes(text: str, schemes: list[dict[str, Any]]) -> list[str]:
    t = norm(text)
    found: list[str] = []
    for s in schemes:
        sid = s["scheme_id"]
        names = [s.get(k) for k in ("name_en", "name_hi", "name_kn", "name_ta") if s.get(k)]
        aliases = SCHEME_ALIASES.get(sid, [])
        if sid.lower() in t.lower() or _has(t, [n.lower() if re.search(r"[A-Za-z]", n) else n for n in names]) \
                or _has(t, aliases):
            found.append(sid)
    # "girls' scholarship" should not also pull the generic scholarship / pension hits
    if "SCH-SCH-01" in found and "SCH-PEN-01" in found and not _has(t, ["pension", "पेंशन", "ಪಿಂಚಣಿ", "ஓய்வூதிய"]):
        found.remove("SCH-PEN-01")
    if not found:
        for btype, words in BENEFIT_TYPE_WORDS.items():
            if _has(t, words):
                found.extend(s["scheme_id"] for s in schemes if s.get("benefit_type") == btype)
    return list(dict.fromkeys(found))


# ------------------------------------------------------------------ booking dates
WEEKDAY_WORDS: dict[int, list[str]] = {
    0: ["monday", "somvar", "somvaar", "सोमवार", "ಸೋಮವಾರ", "திங்கள்"],
    1: ["tuesday", "mangalvar", "mangalvaar", "मंगलवार", "ಮಂಗಳವಾರ", "செவ்வாய்"],
    2: ["wednesday", "budhvar", "budhvaar", "बुधवार", "ಬುಧವಾರ", "புதன்"],
    3: ["thursday", "guruvar", "guruvaar", "गुरुवार", "ಗುರುವಾರ", "வியாழன்"],
    4: ["friday", "shukravar", "shukravaar", "शुक्रवार", "ಶುಕ್ರವಾರ", "வெள்ளி"],
    5: ["saturday", "shanivar", "shanivaar", "शनिवार", "ಶನಿವಾರ", "சனி"],
    6: ["sunday", "ravivar", "ravivaar", "रविवार", "ಭಾನುವಾರ", "ஞாயிறு"],
}


def requested_day(text: str, today: date) -> tuple[date | None, int | None]:
    """Return (date, requested weekday) for 'this Saturday', 'kal', '25 Nov', '2026-11-28'..."""
    t = norm(text).lower()
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", t)
    if m:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))), None
    months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    m = re.search(r"\b(\d{1,2})\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", t)
    if m:
        d = date(today.year, months.index(m.group(2)) + 1, int(m.group(1)))
        if d < today:
            d = d.replace(year=today.year + 1)
        return d, None
    if _has(t, ["day after tomorrow", "parso", "परसों", "ನಾಳಿದ್ದು", "நாளை மறுநாள்"]):
        return today + timedelta(days=2), None
    if _has(t, ["tomorrow", "kal", "कल", "ನಾಳೆ", "நாளை"]):
        return today + timedelta(days=1), None
    for wd, words in WEEKDAY_WORDS.items():
        if _has(t, words):
            delta = (wd - today.weekday()) % 7
            if _has(t, ["next", "agle", "अगले", "ಮುಂದಿನ", "அடுத்த"]) and delta == 0:
                delta = 7
            return today + timedelta(days=delta), wd
    return None, None


def requested_time(text: str) -> tuple[int, int] | None:
    t = norm(text).lower()
    m = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|baje|बजे)", t)
    if m:
        h = int(m.group(1)) % 12 if m.group(3) in ("am", "pm") else int(m.group(1))
        if m.group(3) == "pm":
            h += 12
        if m.group(3) in ("baje", "बजे") and h < 8:
            h += 12
        return h, int(m.group(2) or 0)
    m = re.search(r"\b(\d{1,2}):(\d{2})\b", t)
    if m:
        return int(m.group(1)), int(m.group(2))
    if _has(t, ["morning", "subah", "सुबह", "ಬೆಳಿಗ್ಗೆ", "காலை"]):
        return 10, 0
    if _has(t, ["afternoon", "dopahar", "दोपहर", "ಮಧ್ಯಾಹ್ನ", "மதியம்"]):
        return 14, 0
    if _has(t, ["evening", "shaam", "शाम", "ಸಂಜೆ", "மாலை"]):
        return 16, 0
    return None


def other_citizen_ids(text: str, own_id: str | None) -> list[str]:
    ids = re.findall(r"\b(?:C\d{4}|USR-[0-9A-F]{32})\b", norm(text), flags=re.I)
    return [i.upper() for i in ids if i.upper() != (own_id or "").upper()]


def signals(text: str) -> dict[str, bool]:
    t = norm(text)
    s = {
        "fraud": _has(t, FRAUD) or bool(re.search(r"(pay|send|transfer)\s*(₹|rs\.?)\s*\d+", t, re.I)
                                          and re.search(r"release|agent|call|someone|man|woman|says|said", t, re.I)),
        "bribe": _has(t, BRIBE),
        "rejection": _has(t, REJECTION),
        "delay": _has(t, DELAY),
        "human": _has(t, HUMAN),
        "repeated": _has(t, REPEATED),
        "frustrated": _has(t, FRUSTRATION),
        "distress": _has(t, DISTRESS),
        "legal": _has(t, LEGAL),
        "out_of_scope": _has(t, OUT_OF_SCOPE),
        "secret": _has(t, SECRET),
        "other_person": _has(t, OTHER_PERSON),
        "book": _has(t, BOOK) and (_has(t, CENTRE) or _has(t, ["slot", "appointment", "visit", "बुक", "ಬುಕ್", "முன்பதிவு"])),
        "cancel": _has(t, CANCEL),
        "remind": _has(t, REMIND),
        "draft": _has(t, DRAFT),
        "documents": _has(t, DOCUMENTS),
        "how_apply": _has(t, HOW_APPLY),
        "deadline": _has(t, DEADLINE),
        "app_status": _has(t, APP_STATUS),
        "eligibility": _has(t, ELIGIBILITY),
        "discovery": _has(t, DISCOVERY),
        "scheme_word": _has(t, SCHEME_WORDS),
        "confirm_typed": _has(t, CONFIRM_WORDS) and len(t) < 40,
        "greeting": _has(t, GREETING) and len(t.split()) <= 3,
        "scheme_info": _has(t, SCHEME_INFO),
        "self_marker": _has(t, SELF_MARKERS),
        "centre_info": _has(t, CENTRE) and _has(t, ["where", "nearest", "kahan", "कहाँ", "कहां", "ಎಲ್ಲಿ", "எங்கே", "list", "which"]),
    }
    # a fraud report about an agent/caller is not a grievance against an official
    if s["fraud"] and not re.search(r"officer|adhikari|अधिकारी|babu|clerk|ಅಧಿಕಾರಿ|அதிகாரி|அலுவலர்", t, re.I):
        s["bribe"] = False
    return s


def content_words(text: str) -> list[str]:
    stop = set("""the a an is are was for of to in on and or with my our your i you we can could will would what which
    when where how who there any this that it me please tell about scheme schemes yojana get give need do does
    have has from be kya hai ke ki ka ko liye""".split())
    return [w for w in re.findall(r"[a-z][a-z\-]{3,}", norm(text).lower()) if w not in stop]
