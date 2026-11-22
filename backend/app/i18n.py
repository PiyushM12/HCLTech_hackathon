"""Citizen-facing text in English, Hindi, Kannada, Tamil and Hinglish (R6).

Structured answers are filled from tool output by code, so numbers, dates, amounts and
source IDs are identical in every language by construction. Keep sentences short."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

LANGS = ("en", "hi", "kn", "ta", "hinglish")

T: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ eligibility
    "caveat": {
        "en": "The department makes the final decision.",
        "hi": "अंतिम निर्णय विभाग का होगा।",
        "kn": "ಅಂತಿಮ ನಿರ್ಧಾರ ಇಲಾಖೆಯದ್ದು.",
        "ta": "இறுதி முடிவை துறை எடுக்கும்.",
        "hinglish": "Antim faisla vibhag ka hi hoga.",
    },
    "verdict_appears": {
        "en": "{name}: based on the scheme rules, appears eligible to apply.",
        "hi": "{name}: योजना के नियमों के अनुसार आवेदन करने के पात्र लगते हैं।",
        "kn": "{name}: ಯೋಜನೆಯ ನಿಯಮಗಳ ಪ್ರಕಾರ ಅರ್ಜಿ ಸಲ್ಲಿಸಲು ಅರ್ಹರಾಗಿರುವಂತೆ ಕಾಣುತ್ತದೆ.",
        "ta": "{name}: திட்ட விதிகளின்படி விண்ணப்பிக்கத் தகுதி உடையவராகத் தெரிகிறது.",
        "hinglish": "{name}: scheme ke niyamon ke hisaab se aavedan karne ke liye paatra lagte hain.",
    },
    "verdict_not": {
        "en": "{name}: does not appear eligible. Reason: {reason}.",
        "hi": "{name}: पात्र नहीं लगते। कारण: {reason}।",
        "kn": "{name}: ಅರ್ಹರಾಗಿರುವಂತೆ ಕಾಣುವುದಿಲ್ಲ. ಕಾರಣ: {reason}.",
        "ta": "{name}: தகுதி இல்லை எனத் தெரிகிறது. காரணம்: {reason}.",
        "hinglish": "{name}: paatra nahi lagte. Kaaran: {reason}.",
    },
    "verdict_need": {
        "en": "{name}: I still need {attrs} to check this.",
        "hi": "{name}: जाँच के लिए अभी {attrs} की जानकारी चाहिए।",
        "kn": "{name}: ಪರಿಶೀಲಿಸಲು ಇನ್ನೂ {attrs} ಮಾಹಿತಿ ಬೇಕು.",
        "ta": "{name}: சரிபார்க்க இன்னும் {attrs} விவரம் தேவை.",
        "hinglish": "{name}: check karne ke liye abhi {attrs} ki jaankari chahiye.",
    },
    "verdict_verify": {
        "en": "{name}: this result is provisional. A newer circular ({sources}) changes the rules, so an officer must verify it.",
        "hi": "{name}: यह परिणाम अस्थायी है। नए परिपत्र ({sources}) से नियम बदले हैं, इसलिए अधिकारी इसकी जाँच करेंगे।",
        "kn": "{name}: ಈ ಫಲಿತಾಂಶ ತಾತ್ಕಾಲಿಕ. ಹೊಸ ಸುತ್ತೋಲೆ ({sources}) ನಿಯಮಗಳನ್ನು ಬದಲಿಸಿದೆ, ಆದ್ದರಿಂದ ಅಧಿಕಾರಿ ಪರಿಶೀಲಿಸಬೇಕು.",
        "ta": "{name}: இந்த முடிவு தற்காலிகமானது. புதிய சுற்றறிக்கை ({sources}) விதிகளை மாற்றியுள்ளது, எனவே அலுவலர் சரிபார்க்க வேண்டும்.",
        "hinglish": "{name}: yeh nateeja abhi pakka nahi hai. Naye circular ({sources}) se niyam badle hain, isliye officer ise jaanchenge.",
    },
    "you_told_me": {
        "en": "You told me: {facts}.",
        "hi": "आपने बताया: {facts}।",
        "kn": "ನೀವು ತಿಳಿಸಿದ್ದು: {facts}.",
        "ta": "நீங்கள் கூறியது: {facts}.",
        "hinglish": "Aapne bataya: {facts}.",
    },
    "given": {
        "en": "you told me {a}", "hi": "आपने बताया {a}", "kn": "ನೀವು ತಿಳಿಸಿದ್ದು {a}",
        "ta": "நீங்கள் கூறியது {a}", "hinglish": "aapne bataya {a}",
    },
    "rule_failed_also_closed": {
        "en": "Note: {name} is not accepting applications on {date}.",
        "hi": "ध्यान दें: {date} को {name} में आवेदन नहीं लिए जा रहे हैं।",
        "kn": "ಗಮನಿಸಿ: {date} ರಂದು {name} ಅರ್ಜಿಗಳನ್ನು ಸ್ವೀಕರಿಸುತ್ತಿಲ್ಲ.",
        "ta": "கவனிக்க: {date} அன்று {name} விண்ணப்பங்களை ஏற்கவில்லை.",
        "hinglish": "Dhyan dein: {date} ko {name} mein aavedan nahi liye ja rahe hain.",
    },
    "provisional_referred": {
        "en": "Because the result is provisional, I have sent it to an officer to check (reference {rid}).",
        "hi": "परिणाम अस्थायी है, इसलिए मैंने इसे जाँच के लिए अधिकारी को भेज दिया है (संदर्भ {rid})।",
        "kn": "ಫಲಿತಾಂಶ ತಾತ್ಕಾಲಿಕವಾದ್ದರಿಂದ, ಪರಿಶೀಲನೆಗಾಗಿ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ (ಉಲ್ಲೇಖ {rid}).",
        "ta": "முடிவு தற்காலிகமானது என்பதால், சரிபார்க்க அலுவலருக்கு அனுப்பியுள்ளேன் (குறிப்பு {rid}).",
        "hinglish": "Nateeja pakka nahi hai, isliye maine ise jaanch ke liye officer ko bhej diya hai (reference {rid}).",
    },
    # ------------------------------------------------------------------ discovery
    "disc_intro": {
        "en": "Based on what you told me, this is what the scheme rules say:",
        "hi": "आपकी दी गई जानकारी के आधार पर योजनाओं के नियम यह बताते हैं:",
        "kn": "ನೀವು ನೀಡಿದ ಮಾಹಿತಿಯ ಆಧಾರದಲ್ಲಿ ಯೋಜನೆಗಳ ನಿಯಮಗಳು ಹೀಗೆ ಹೇಳುತ್ತವೆ:",
        "ta": "நீங்கள் கொடுத்த விவரங்களின் அடிப்படையில் திட்ட விதிகள் சொல்வது:",
        "hinglish": "Aapki di gayi jaankari ke hisaab se schemes ke niyam yeh kehte hain:",
    },
    "disc_eligible_header": {
        "en": "You appear eligible to apply for:",
        "hi": "आप इन योजनाओं के लिए आवेदन करने के पात्र लगते हैं:",
        "kn": "ನೀವು ಈ ಯೋಜನೆಗಳಿಗೆ ಅರ್ಜಿ ಸಲ್ಲಿಸಲು ಅರ್ಹರಾಗಿರುವಂತೆ ಕಾಣುತ್ತದೆ:",
        "ta": "நீங்கள் இந்தத் திட்டங்களுக்கு விண்ணப்பிக்கத் தகுதி உடையவராகத் தெரிகிறது:",
        "hinglish": "Aap in schemes ke liye aavedan karne ke paatra lagte hain:",
    },
    "disc_maybe_header": {
        "en": "These may also fit, but I need more details:",
        "hi": "ये योजनाएँ भी हो सकती हैं, पर और जानकारी चाहिए:",
        "kn": "ಇವೂ ಸರಿಹೊಂದಬಹುದು, ಆದರೆ ಇನ್ನಷ್ಟು ಮಾಹಿತಿ ಬೇಕು:",
        "ta": "இவையும் பொருந்தக்கூடும், ஆனால் மேலும் விவரங்கள் தேவை:",
        "hinglish": "Yeh schemes bhi ho sakti hain, par aur jaankari chahiye:",
    },
    "disc_verify_header": {
        "en": "Provisional (an officer must verify because of a newer circular):",
        "hi": "अस्थायी (नए परिपत्र के कारण अधिकारी जाँच करेंगे):",
        "kn": "ತಾತ್ಕಾಲಿಕ (ಹೊಸ ಸುತ್ತೋಲೆಯ ಕಾರಣ ಅಧಿಕಾರಿ ಪರಿಶೀಲಿಸಬೇಕು):",
        "ta": "தற்காலிகம் (புதிய சுற்றறிக்கை காரணமாக அலுவலர் சரிபார்க்க வேண்டும்):",
        "hinglish": "Abhi pakka nahi (naye circular ki wajah se officer jaanchenge):",
    },
    "disc_upcoming_header": {
        "en": "Opening soon:", "hi": "जल्द खुलने वाली योजनाएँ:", "kn": "ಶೀಘ್ರದಲ್ಲೇ ತೆರೆಯಲಿದೆ:",
        "ta": "விரைவில் திறக்கப்படும்:", "hinglish": "Jald khulne wali schemes:",
    },
    "disc_none": {
        "en": "With these details, you do not appear eligible for any scheme that is open now.",
        "hi": "इन जानकारियों के साथ आप अभी खुली किसी योजना के पात्र नहीं लगते।",
        "kn": "ಈ ವಿವರಗಳೊಂದಿಗೆ, ಈಗ ತೆರೆದಿರುವ ಯಾವುದೇ ಯೋಜನೆಗೆ ನೀವು ಅರ್ಹರಾಗಿರುವಂತೆ ಕಾಣುವುದಿಲ್ಲ.",
        "ta": "இந்த விவரங்களுடன், இப்போது திறந்திருக்கும் எந்தத் திட்டத்திற்கும் நீங்கள் தகுதி பெறவில்லை எனத் தெரிகிறது.",
        "hinglish": "In jaankariyon ke saath aap abhi khuli kisi scheme ke paatra nahi lagte.",
    },
    "disc_not_count": {
        "en": "{n} other open schemes do not match (for example {example}).",
        "hi": "{n} अन्य खुली योजनाएँ मेल नहीं खातीं (जैसे {example})।",
        "kn": "{n} ಇತರ ತೆರೆದ ಯೋಜನೆಗಳು ಹೊಂದುವುದಿಲ್ಲ (ಉದಾ: {example}).",
        "ta": "{n} பிற திறந்த திட்டங்கள் பொருந்தவில்லை (உதா: {example}).",
        "hinglish": "{n} aur khuli schemes match nahi karti (jaise {example}).",
    },
    "benefit": {
        "en": "Benefit: {benefit}", "hi": "लाभ: {benefit}", "kn": "ಸೌಲಭ್ಯ: {benefit}",
        "ta": "பயன்: {benefit}", "hinglish": "Fayda: {benefit}",
    },
    "needs": {
        "en": "needs: {attrs}", "hi": "चाहिए: {attrs}", "kn": "ಬೇಕು: {attrs}",
        "ta": "தேவை: {attrs}", "hinglish": "chahiye: {attrs}",
    },
    # ------------------------------------------------------------------ dates / status
    "last_date": {
        "en": "Last date to apply: {date}.", "hi": "आवेदन की अंतिम तिथि: {date}।",
        "kn": "ಅರ್ಜಿ ಸಲ್ಲಿಸಲು ಕೊನೆಯ ದಿನಾಂಕ: {date}.", "ta": "விண்ணப்பிக்க கடைசி தேதி: {date}.",
        "hinglish": "Aavedan ki aakhri tareekh: {date}.",
    },
    "open_all_year": {
        "en": "Applications are open all year.", "hi": "आवेदन पूरे साल खुले हैं।",
        "kn": "ಅರ್ಜಿಗಳು ವರ್ಷವಿಡೀ ತೆರೆದಿವೆ.", "ta": "விண்ணப்பங்கள் ஆண்டு முழுவதும் ஏற்கப்படும்.",
        "hinglish": "Aavedan poore saal khule hain.",
    },
    "st_open": {
        "en": "{name} is open for applications.", "hi": "{name} में अभी आवेदन खुले हैं।",
        "kn": "{name} ಗೆ ಈಗ ಅರ್ಜಿಗಳು ತೆರೆದಿವೆ.", "ta": "{name} க்கு இப்போது விண்ணப்பங்கள் திறந்துள்ளன.",
        "hinglish": "{name} mein abhi aavedan khule hain.",
    },
    "st_deadline_passed": {
        "en": "{name}: the last date was {date}, so applications are now closed.",
        "hi": "{name}: अंतिम तिथि {date} थी, इसलिए अब आवेदन बंद हैं।",
        "kn": "{name}: ಕೊನೆಯ ದಿನಾಂಕ {date} ಆಗಿತ್ತು, ಆದ್ದರಿಂದ ಈಗ ಅರ್ಜಿಗಳು ಮುಚ್ಚಿವೆ.",
        "ta": "{name}: கடைசி தேதி {date}, எனவே இப்போது விண்ணப்பங்கள் மூடப்பட்டுள்ளன.",
        "hinglish": "{name}: aakhri tareekh {date} thi, isliye ab aavedan band hain.",
    },
    "st_closed_circular": {
        "en": "{name} is closed for new applications from {date} ({source}).",
        "hi": "{name} में {date} से नए आवेदन बंद हैं ({source})।",
        "kn": "{name} ಗೆ {date} ರಿಂದ ಹೊಸ ಅರ್ಜಿಗಳು ಮುಚ್ಚಿವೆ ({source}).",
        "ta": "{name} க்கு {date} முதல் புதிய விண்ணப்பங்கள் மூடப்பட்டுள்ளன ({source}).",
        "hinglish": "{name} mein {date} se naye aavedan band hain ({source}).",
    },
    "st_closed": {
        "en": "{name} is closed for applications.", "hi": "{name} में आवेदन बंद हैं।",
        "kn": "{name} ಗೆ ಅರ್ಜಿಗಳು ಮುಚ್ಚಿವೆ.", "ta": "{name} க்கு விண்ணப்பங்கள் மூடப்பட்டுள்ளன.",
        "hinglish": "{name} mein aavedan band hain.",
    },
    "st_upcoming": {
        "en": "{name} is not open yet. Applications open on {date}.",
        "hi": "{name} अभी शुरू नहीं हुई है। आवेदन {date} से शुरू होंगे।",
        "kn": "{name} ಇನ್ನೂ ಆರಂಭವಾಗಿಲ್ಲ. ಅರ್ಜಿಗಳು {date} ರಿಂದ ಆರಂಭ.",
        "ta": "{name} இன்னும் தொடங்கவில்லை. விண்ணப்பங்கள் {date} முதல் தொடங்கும்.",
        "hinglish": "{name} abhi shuru nahi hui hai. Aavedan {date} se shuru honge.",
    },
    "st_extended": {
        "en": "The last date was extended from {old} to {new} ({source}).",
        "hi": "अंतिम तिथि {old} से बढ़ाकर {new} कर दी गई है ({source})।",
        "kn": "ಕೊನೆಯ ದಿನಾಂಕವನ್ನು {old} ರಿಂದ {new} ಕ್ಕೆ ವಿಸ್ತರಿಸಲಾಗಿದೆ ({source}).",
        "ta": "கடைசி தேதி {old} இலிருந்து {new} ஆக நீட்டிக்கப்பட்டுள்ளது ({source}).",
        "hinglish": "Aakhri tareekh {old} se badhakar {new} kar di gayi hai ({source}).",
    },
    "st_today": {
        "en": "Today ({date}) is the last date, so please apply today.",
        "hi": "आज ({date}) अंतिम तिथि है, इसलिए कृपया आज ही आवेदन करें।",
        "kn": "ಇಂದು ({date}) ಕೊನೆಯ ದಿನಾಂಕ, ದಯವಿಟ್ಟು ಇಂದೇ ಅರ್ಜಿ ಸಲ್ಲಿಸಿ.",
        "ta": "இன்று ({date}) கடைசி தேதி, எனவே இன்றே விண்ணப்பிக்கவும்.",
        "hinglish": "Aaj ({date}) aakhri tareekh hai, isliye kripya aaj hi aavedan karein.",
    },
    "st_days_left": {
        "en": "{n} days are left.", "hi": "{n} दिन बाकी हैं।", "kn": "{n} ದಿನಗಳು ಉಳಿದಿವೆ.",
        "ta": "{n} நாட்கள் உள்ளன.", "hinglish": "{n} din baaki hain.",
    },
    "upcoming_change": {
        "en": "Note: a change takes effect on {date} ({source}).",
        "hi": "ध्यान दें: {date} से एक बदलाव लागू होगा ({source})।",
        "kn": "ಗಮನಿಸಿ: {date} ರಿಂದ ಒಂದು ಬದಲಾವಣೆ ಜಾರಿಗೆ ಬರುತ್ತದೆ ({source}).",
        "ta": "கவனிக்க: {date} முதல் ஒரு மாற்றம் அமலுக்கு வரும் ({source}).",
        "hinglish": "Dhyan dein: {date} se ek badlav laagu hoga ({source}).",
    },
    "upcoming_rule": {
        "en": "From {date}, {rule} ({source}).",
        "hi": "{date} से: {rule} ({source})।",
        "kn": "{date} ರಿಂದ: {rule} ({source}).",
        "ta": "{date} முதல்: {rule} ({source}).",
        "hinglish": "{date} se: {rule} ({source}).",
    },
    # ------------------------------------------------------------------ documents / info
    "doc_header": {
        "en": "Documents needed for {name}:", "hi": "{name} के लिए ज़रूरी दस्तावेज़:",
        "kn": "{name} ಗೆ ಬೇಕಾದ ದಾಖಲೆಗಳು:", "ta": "{name} க்குத் தேவையான ஆவணங்கள்:",
        "hinglish": "{name} ke liye zaroori documents:",
    },
    "mandatory": {"en": "(must)", "hi": "(ज़रूरी)", "kn": "(ಕಡ್ಡಾಯ)", "ta": "(கட்டாயம்)", "hinglish": "(zaroori)"},
    "optional": {"en": "(optional)", "hi": "(वैकल्पिक)", "kn": "(ಐಚ್ಛಿಕ)", "ta": "(விருப்பத்தேர்வு)", "hinglish": "(optional)"},
    "term_income_certificate": {
        "en": "An income certificate is a paper from the Tehsildar's office that states your family's yearly income.",
        "hi": "आय प्रमाण पत्र तहसील कार्यालय से मिलने वाला वह काग़ज़ है जिसमें परिवार की सालाना आय लिखी होती है।",
        "kn": "ಆದಾಯ ಪ್ರಮಾಣಪತ್ರ ಎಂದರೆ ಕುಟುಂಬದ ವಾರ್ಷಿಕ ಆದಾಯವನ್ನು ತಿಳಿಸುವ, ತಹಶೀಲ್ದಾರ್ ಕಚೇರಿ ನೀಡುವ ದಾಖಲೆ.",
        "ta": "வருமானச் சான்றிதழ் என்பது குடும்பத்தின் ஆண்டு வருமானத்தைக் குறிப்பிடும், வட்டாட்சியர் அலுவலகம் வழங்கும் ஆவணம்.",
        "hinglish": "Income certificate tehsil office se milne wala kaagaz hai jismein parivaar ki saalana aamdani likhi hoti hai.",
    },
    "apply_free": {
        "en": "You can apply free of cost at any service centre.",
        "hi": "आप किसी भी सेवा केंद्र पर मुफ़्त में आवेदन कर सकते हैं।",
        "kn": "ಯಾವುದೇ ಸೇವಾ ಕೇಂದ್ರದಲ್ಲಿ ಉಚಿತವಾಗಿ ಅರ್ಜಿ ಸಲ್ಲಿಸಬಹುದು.",
        "ta": "எந்த சேவை மையத்திலும் இலவசமாக விண்ணப்பிக்கலாம்.",
        "hinglish": "Aap kisi bhi seva kendra par muft mein aavedan kar sakte hain.",
    },
    "who_can_apply": {
        "en": "Who can apply (main rules):", "hi": "कौन आवेदन कर सकता है (मुख्य नियम):",
        "kn": "ಯಾರು ಅರ್ಜಿ ಸಲ್ಲಿಸಬಹುದು (ಮುಖ್ಯ ನಿಯಮಗಳು):", "ta": "யார் விண்ணப்பிக்கலாம் (முக்கிய விதிகள்):",
        "hinglish": "Kaun aavedan kar sakta hai (mukhya niyam):",
    },
    "at_least_one_of": {
        "en": "at least one of: {items}", "hi": "इनमें से कम से कम एक: {items}",
        "kn": "ಇವುಗಳಲ್ಲಿ ಕನಿಷ್ಠ ಒಂದು: {items}", "ta": "இவற்றில் குறைந்தது ஒன்று: {items}",
        "hinglish": "inmein se kam se kam ek: {items}",
    },
    "or": {"en": " or ", "hi": " या ", "kn": " ಅಥವಾ ", "ta": " அல்லது ", "hinglish": " ya "},
    "docs_pointer": {
        "en": "Ask me \"documents for {name}\" for the full checklist.",
        "hi": "पूरी सूची के लिए पूछें: \"{name} के दस्तावेज़\"।",
        "kn": "ಪೂರ್ಣ ಪಟ್ಟಿಗಾಗಿ ಕೇಳಿ: \"{name} ದಾಖಲೆಗಳು\".",
        "ta": "முழுப் பட்டியலுக்கு கேளுங்கள்: \"{name} ஆவணங்கள்\".",
        "hinglish": "Poori list ke liye poochhiye: \"{name} ke documents\".",
    },
    "general_intro": {
        "en": "Here is what the scheme documents say:", "hi": "योजना के दस्तावेज़ों के अनुसार:",
        "kn": "ಯೋಜನಾ ದಾಖಲೆಗಳ ಪ್ರಕಾರ:", "ta": "திட்ட ஆவணங்களின்படி:",
        "hinglish": "Scheme ke documents ke hisaab se:",
    },
    "ask_scheme": {
        "en": "Which scheme do you mean? For example: {examples}.",
        "hi": "आप किस योजना के बारे में पूछ रहे हैं? जैसे: {examples}।",
        "kn": "ನೀವು ಯಾವ ಯೋಜನೆಯ ಬಗ್ಗೆ ಕೇಳುತ್ತಿದ್ದೀರಿ? ಉದಾ: {examples}.",
        "ta": "நீங்கள் எந்தத் திட்டத்தைப் பற்றிக் கேட்கிறீர்கள்? உதா: {examples}.",
        "hinglish": "Aap kis scheme ke baare mein pooch rahe hain? Jaise: {examples}.",
    },
    "app_status_line": {
        "en": "Application {id} for {name}: status {status} (updated {date}).",
        "hi": "{name} के लिए आवेदन {id}: स्थिति {status} ({date} को अपडेट)।",
        "kn": "{name} ಗಾಗಿ ಅರ್ಜಿ {id}: ಸ್ಥಿತಿ {status} ({date} ರಂದು ನವೀಕರಿಸಲಾಗಿದೆ).",
        "ta": "{name} க்கான விண்ணப்பம் {id}: நிலை {status} ({date} அன்று புதுப்பிக்கப்பட்டது).",
        "hinglish": "{name} ke liye aavedan {id}: status {status} ({date} ko update).",
    },
    "app_none": {
        "en": "I could not find any application in your name.",
        "hi": "आपके नाम से कोई आवेदन नहीं मिला।",
        "kn": "ನಿಮ್ಮ ಹೆಸರಿನಲ್ಲಿ ಯಾವುದೇ ಅರ್ಜಿ ಕಂಡುಬಂದಿಲ್ಲ.",
        "ta": "உங்கள் பெயரில் எந்த விண்ணப்பமும் இல்லை.",
        "hinglish": "Aapke naam se koi aavedan nahi mila.",
    },
    "app_delay": {
        "en": "This is beyond the {days}-day processing target, so I have referred it to an officer.",
        "hi": "यह {days} दिन की तय समय-सीमा से ज़्यादा है, इसलिए मैंने इसे अधिकारी को भेज दिया है।",
        "kn": "ಇದು {days} ದಿನಗಳ ನಿಗದಿತ ಅವಧಿಯನ್ನು ಮೀರಿದೆ, ಆದ್ದರಿಂದ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ.",
        "ta": "இது {days} நாள் இலக்கைத் தாண்டிவிட்டது, எனவே அலுவலருக்கு அனுப்பியுள்ளேன்.",
        "hinglish": "Yeh {days} din ki tay samay-seema se zyada hai, isliye maine ise officer ko bhej diya hai.",
    },
    # ------------------------------------------------------------------ clarification
    "clar_intro": {
        "en": "To check this, I need a little more information:",
        "hi": "जाँच के लिए मुझे थोड़ी और जानकारी चाहिए:",
        "kn": "ಪರಿಶೀಲಿಸಲು ನನಗೆ ಇನ್ನೂ ಸ್ವಲ್ಪ ಮಾಹಿತಿ ಬೇಕು:",
        "ta": "இதைச் சரிபார்க்க எனக்கு இன்னும் சில விவரங்கள் தேவை:",
        "hinglish": "Check karne ke liye mujhe thodi aur jaankari chahiye:",
    },
    "why_ask": {
        "en": "Why I ask: the rules of {schemes} depend on this.",
        "hi": "क्यों पूछ रहा हूँ: {schemes} के नियम इस पर निर्भर हैं।",
        "kn": "ಏಕೆ ಕೇಳುತ್ತಿದ್ದೇನೆ: {schemes} ನಿಯಮಗಳು ಇದನ್ನು ಅವಲಂಬಿಸಿವೆ.",
        "ta": "ஏன் கேட்கிறேன்: {schemes} விதிகள் இதைப் பொறுத்தது.",
        "hinglish": "Kyon pooch raha hoon: {schemes} ke niyam is par nirbhar hain.",
    },
    "q_age": {
        "en": "How old is the person who will apply?", "hi": "आवेदन करने वाले व्यक्ति की उम्र कितनी है?",
        "kn": "ಅರ್ಜಿ ಸಲ್ಲಿಸುವವರ ವಯಸ್ಸು ಎಷ್ಟು?", "ta": "விண்ணப்பிப்பவரின் வயது என்ன?",
        "hinglish": "Aavedan karne wale ki umar kitni hai?",
    },
    "q_annual_household_income": {
        "en": "What is your family's total yearly income (all members together)?",
        "hi": "आपके परिवार की कुल सालाना आय (सभी सदस्यों की मिलाकर) कितनी है?",
        "kn": "ನಿಮ್ಮ ಕುಟುಂಬದ ಒಟ್ಟು ವಾರ್ಷಿಕ ಆದಾಯ (ಎಲ್ಲ ಸದಸ್ಯರದು ಸೇರಿ) ಎಷ್ಟು?",
        "ta": "உங்கள் குடும்பத்தின் மொத்த ஆண்டு வருமானம் (அனைவரும் சேர்த்து) எவ்வளவு?",
        "hinglish": "Aapke parivaar ki kul saalana aamdani (sab sadasya milaakar) kitni hai?",
    },
    "q_land_holding_acres": {
        "en": "How much farm land does the family own, in acres?", "hi": "परिवार के पास कितने एकड़ ज़मीन है?",
        "kn": "ಕುಟುಂಬದ ಬಳಿ ಎಷ್ಟು ಎಕರೆ ಜಮೀನು ಇದೆ?", "ta": "குடும்பத்திடம் எத்தனை ஏக்கர் நிலம் உள்ளது?",
        "hinglish": "Parivaar ke paas kitne acre zameen hai?",
    },
    "q_gender": {
        "en": "Is the applicant female, male or other?", "hi": "आवेदक महिला हैं, पुरुष हैं या अन्य?",
        "kn": "ಅರ್ಜಿದಾರರು ಮಹಿಳೆಯೇ, ಪುರುಷರೇ ಅಥವಾ ಇತರರೇ?", "ta": "விண்ணப்பதாரர் பெண்ணா, ஆணா அல்லது பிறரா?",
        "hinglish": "Aavedak mahila hain, purush ya anya?",
    },
    "q_occupation": {
        "en": "What work does the applicant do (for example farmer, student, daily-wage worker)?",
        "hi": "आवेदक क्या काम करते हैं (जैसे किसान, विद्यार्थी, दिहाड़ी मज़दूर)?",
        "kn": "ಅರ್ಜಿದಾರರು ಯಾವ ಕೆಲಸ ಮಾಡುತ್ತಾರೆ (ಉದಾ: ರೈತ, ವಿದ್ಯಾರ್ಥಿ, ಕೂಲಿ ಕಾರ್ಮಿಕ)?",
        "ta": "விண்ணப்பதாரர் என்ன வேலை செய்கிறார் (உதா: விவசாயி, மாணவர், கூலித் தொழிலாளி)?",
        "hinglish": "Aavedak kya kaam karte hain (jaise kisan, student, mazdoor)?",
    },
    "q_residence_type": {
        "en": "Do you live in a village (rural) or a town or city (urban)?",
        "hi": "आप गाँव में रहते हैं या शहर में?", "kn": "ನೀವು ಹಳ್ಳಿಯಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಾ ಅಥವಾ ನಗರದಲ್ಲಿ?",
        "ta": "நீங்கள் கிராமத்தில் வசிக்கிறீர்களா அல்லது நகரத்திலா?", "hinglish": "Aap gaon mein rehte hain ya shahar mein?",
    },
    "q_district": {
        "en": "Which district do you live in (Nayagaon, Sundarpur, Kaverinadu or Thenpuram)?",
        "hi": "आप किस ज़िले में रहते हैं (नयागाँव, सुंदरपुर, कावेरीनाडु या तेनपुरम)?",
        "kn": "ನೀವು ಯಾವ ಜಿಲ್ಲೆಯಲ್ಲಿ ವಾಸಿಸುತ್ತೀರಿ (ನಯಾಗಾಂವ್, ಸುಂದರಪುರ, ಕಾವೇರಿನಾಡು ಅಥವಾ ತೆನ್ಪುರಂ)?",
        "ta": "நீங்கள் எந்த மாவட்டத்தில் வசிக்கிறீர்கள் (நயாகாவ், சுந்தர்பூர், காவேரிநாடு அல்லது தென்புரம்)?",
        "hinglish": "Aap kis zile mein rehte hain (Nayagaon, Sundarpur, Kaverinadu ya Thenpuram)?",
    },
    "q_category": {
        "en": "Does the family belong to the SC or ST category? You may skip this question.",
        "hi": "क्या परिवार अनुसूचित जाति (SC) या अनुसूचित जनजाति (ST) वर्ग से है? आप चाहें तो यह न बताएँ।",
        "kn": "ಕುಟುಂಬವು ಪರಿಶಿಷ್ಟ ಜಾತಿ (SC) ಅಥವಾ ಪರಿಶಿಷ್ಟ ಪಂಗಡ (ST) ವರ್ಗಕ್ಕೆ ಸೇರಿದೆಯೇ? ಬೇಡವಾದರೆ ಉತ್ತರಿಸಬೇಕಿಲ್ಲ.",
        "ta": "குடும்பம் பட்டியல் சாதி (SC) அல்லது பழங்குடி (ST) பிரிவைச் சேர்ந்ததா? விரும்பாவிட்டால் பதில் சொல்ல வேண்டாம்.",
        "hinglish": "Kya parivaar SC ya ST varg se hai? Aap chahein to yeh na batayein.",
    },
    "q_is_disabled": {
        "en": "Does the applicant have a disability?", "hi": "क्या आवेदक दिव्यांग हैं?",
        "kn": "ಅರ್ಜಿದಾರರಿಗೆ ಅಂಗವೈಕಲ್ಯ ಇದೆಯೇ?", "ta": "விண்ணப்பதாரர் மாற்றுத்திறனாளியா?",
        "hinglish": "Kya aavedak divyang hain?",
    },
    "q_disability_percent": {
        "en": "What disability percentage is written on the disability certificate?",
        "hi": "दिव्यांगता प्रमाण पत्र पर कितने प्रतिशत दिव्यांगता लिखी है?",
        "kn": "ಅಂಗವೈಕಲ್ಯ ಪ್ರಮಾಣಪತ್ರದಲ್ಲಿ ಎಷ್ಟು ಶೇಕಡಾ ಅಂಗವೈಕಲ್ಯ ಎಂದು ಬರೆದಿದೆ?",
        "ta": "மாற்றுத்திறன் சான்றிதழில் எத்தனை சதவீதம் என்று எழுதப்பட்டுள்ளது?",
        "hinglish": "Divyangta certificate par kitne pratishat likha hai?",
    },
    "q_scheme": {
        "en": "Which scheme is this for?", "hi": "यह किस योजना के लिए है?", "kn": "ಇದು ಯಾವ ಯೋಜನೆಗಾಗಿ?",
        "ta": "இது எந்தத் திட்டத்திற்கு?", "hinglish": "Yeh kis scheme ke liye hai?",
    },
    "lang_ask": {
        "en": "Which language should I reply in: हिन्दी, English, ಕನ್ನಡ or தமிழ்?",
        "hi": "मैं किस भाषा में जवाब दूँ: हिन्दी, English, ಕನ್ನಡ या தமிழ்?",
        "kn": "ನಾನು ಯಾವ ಭಾಷೆಯಲ್ಲಿ ಉತ್ತರಿಸಲಿ: हिन्दी, English, ಕನ್ನಡ ಅಥವಾ தமிழ்?",
        "ta": "நான் எந்த மொழியில் பதில் தரட்டும்: हिन्दी, English, ಕನ್ನಡ அல்லது தமிழ்?",
        "hinglish": "Main kis bhasha mein jawab doon: हिन्दी, English, ಕನ್ನಡ ya தமிழ்?",
    },
    "partial_unknown": {
        "en": "I could not confirm {attrs}, so I cannot finish the check for {names}.",
        "hi": "{attrs} की पुष्टि नहीं हो पाई, इसलिए {names} की जाँच पूरी नहीं हो सकी।",
        "kn": "{attrs} ದೃಢಪಡಿಸಲು ಆಗಲಿಲ್ಲ, ಆದ್ದರಿಂದ {names} ಪರಿಶೀಲನೆ ಪೂರ್ಣಗೊಳಿಸಲು ಆಗಲಿಲ್ಲ.",
        "ta": "{attrs} உறுதிப்படுத்த முடியவில்லை, எனவே {names} சரிபார்ப்பை முடிக்க முடியவில்லை.",
        "hinglish": "{attrs} confirm nahi ho paya, isliye {names} ki jaanch poori nahi ho saki.",
    },
    # ------------------------------------------------------------------ centres / actions
    "centres_header": {
        "en": "Service centres in {district}:", "hi": "{district} में सेवा केंद्र:",
        "kn": "{district} ನಲ್ಲಿ ಸೇವಾ ಕೇಂದ್ರಗಳು:", "ta": "{district} இல் சேவை மையங்கள்:",
        "hinglish": "{district} mein seva kendra:",
    },
    "book_preview": {
        "en": "I can book this visit for you:\n- Centre: {centre}\n- Address: {address}\n- Time: {slot}\n{reminder_line}{note}Nothing is booked yet. Press Confirm to book it, or Cancel.",
        "hi": "मैं आपके लिए यह मुलाकात बुक कर सकता हूँ:\n- केंद्र: {centre}\n- पता: {address}\n- समय: {slot}\n{reminder_line}{note}अभी कुछ भी बुक नहीं हुआ है। बुक करने के लिए 'पुष्टि करें' दबाएँ, या 'रद्द करें'।",
        "kn": "ನಿಮಗಾಗಿ ಈ ಭೇಟಿಯನ್ನು ಬುಕ್ ಮಾಡಬಹುದು:\n- ಕೇಂದ್ರ: {centre}\n- ವಿಳಾಸ: {address}\n- ಸಮಯ: {slot}\n{reminder_line}{note}ಇನ್ನೂ ಏನೂ ಬುಕ್ ಆಗಿಲ್ಲ. ಬುಕ್ ಮಾಡಲು 'ದೃಢೀಕರಿಸಿ' ಒತ್ತಿ, ಅಥವಾ 'ರದ್ದುಮಾಡಿ'.",
        "ta": "உங்களுக்காக இந்த வருகையை முன்பதிவு செய்யலாம்:\n- மையம்: {centre}\n- முகவரி: {address}\n- நேரம்: {slot}\n{reminder_line}{note}இன்னும் எதுவும் முன்பதிவு செய்யப்படவில்லை. முன்பதிவு செய்ய 'உறுதிப்படுத்து' அழுத்தவும், அல்லது 'ரத்து செய்'.",
        "hinglish": "Main aapke liye yeh visit book kar sakta hoon:\n- Kendra: {centre}\n- Pata: {address}\n- Samay: {slot}\n{reminder_line}{note}Abhi kuch bhi book nahi hua hai. Book karne ke liye Confirm dabaiye, ya Cancel.",
    },
    "reminder_line": {
        "en": "- Reminder: {when}\n", "hi": "- याद दिलाना: {when}\n", "kn": "- ಜ್ಞಾಪನೆ: {when}\n",
        "ta": "- நினைவூட்டல்: {when}\n", "hinglish": "- Reminder: {when}\n",
    },
    "lead_time_note": {
        "en": "Visits must be booked at least {h} hours ahead, so I picked the next possible day.\n",
        "hi": "मुलाकात कम से कम {h} घंटे पहले बुक करनी होती है, इसलिए मैंने अगला संभव दिन चुना है।\n",
        "kn": "ಭೇಟಿಯನ್ನು ಕನಿಷ್ಠ {h} ಗಂಟೆ ಮುಂಚಿತವಾಗಿ ಬುಕ್ ಮಾಡಬೇಕು, ಆದ್ದರಿಂದ ಮುಂದಿನ ಸಾಧ್ಯ ದಿನವನ್ನು ಆರಿಸಿದ್ದೇನೆ.\n",
        "ta": "வருகையை குறைந்தது {h} மணி நேரம் முன்பே முன்பதிவு செய்ய வேண்டும், எனவே அடுத்த சாத்தியமான நாளைத் தேர்ந்தெடுத்துள்ளேன்.\n",
        "hinglish": "Visit kam se kam {h} ghante pehle book karni hoti hai, isliye maine agla sambhav din chuna hai.\n",
    },
    "centre_closed_note": {
        "en": "No centre in {district} is open on the day you asked, so I picked the next working day.\n",
        "hi": "आपके बताए दिन {district} में कोई केंद्र खुला नहीं है, इसलिए मैंने अगला कामकाजी दिन चुना है।\n",
        "kn": "ನೀವು ಕೇಳಿದ ದಿನ {district} ನಲ್ಲಿ ಯಾವುದೇ ಕೇಂದ್ರ ತೆರೆದಿಲ್ಲ, ಆದ್ದರಿಂದ ಮುಂದಿನ ಕೆಲಸದ ದಿನವನ್ನು ಆರಿಸಿದ್ದೇನೆ.\n",
        "ta": "நீங்கள் கேட்ட நாளில் {district} இல் எந்த மையமும் திறந்திருக்காது, எனவே அடுத்த வேலை நாளைத் தேர்ந்தெடுத்துள்ளேன்.\n",
        "hinglish": "Aapke bataye din {district} mein koi kendra khula nahi hai, isliye maine agla kaam ka din chuna hai.\n",
    },
    "draft_preview": {
        "en": "I can prepare a draft application for {name}:\n{fields}\n{missing}The draft will NOT be submitted. Take it with your documents to a service centre. Press Confirm to create the draft.",
        "hi": "मैं {name} के लिए आवेदन का मसौदा (ड्राफ़्ट) बना सकता हूँ:\n{fields}\n{missing}यह ड्राफ़्ट जमा नहीं किया जाएगा। इसे दस्तावेज़ों के साथ सेवा केंद्र पर ले जाएँ। ड्राफ़्ट बनाने के लिए 'पुष्टि करें' दबाएँ।",
        "kn": "{name} ಗಾಗಿ ಅರ್ಜಿಯ ಕರಡು ಸಿದ್ಧಪಡಿಸಬಹುದು:\n{fields}\n{missing}ಈ ಕರಡನ್ನು ಸಲ್ಲಿಸಲಾಗುವುದಿಲ್ಲ. ದಾಖಲೆಗಳೊಂದಿಗೆ ಸೇವಾ ಕೇಂದ್ರಕ್ಕೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ಕರಡು ರಚಿಸಲು 'ದೃಢೀಕರಿಸಿ' ಒತ್ತಿ.",
        "ta": "{name} க்கான விண்ணப்ப வரைவைத் தயாரிக்கலாம்:\n{fields}\n{missing}இந்த வரைவு சமர்ப்பிக்கப்படாது. ஆவணங்களுடன் சேவை மையத்திற்குக் கொண்டு செல்லுங்கள். வரைவை உருவாக்க 'உறுதிப்படுத்து' அழுத்தவும்.",
        "hinglish": "Main {name} ke liye aavedan ka draft bana sakta hoon:\n{fields}\n{missing}Yeh draft jama nahi kiya jayega. Ise documents ke saath seva kendra le jaiye. Draft banane ke liye Confirm dabaiye.",
    },
    "draft_missing": {
        "en": "Still missing: {items}\n", "hi": "अभी बाकी: {items}\n", "kn": "ಇನ್ನೂ ಬೇಕಾದವು: {items}\n",
        "ta": "இன்னும் தேவை: {items}\n", "hinglish": "Abhi baaki: {items}\n",
    },
    "draft_not_eligible": {
        "en": "I will not prepare a draft for {name}, because the rules say you do not appear eligible: {reason}.",
        "hi": "मैं {name} का ड्राफ़्ट नहीं बनाऊँगा, क्योंकि नियमों के अनुसार आप पात्र नहीं लगते: {reason}।",
        "kn": "{name} ಗೆ ಕರಡು ಸಿದ್ಧಪಡಿಸುವುದಿಲ್ಲ, ಏಕೆಂದರೆ ನಿಯಮಗಳ ಪ್ರಕಾರ ನೀವು ಅರ್ಹರಾಗಿರುವಂತೆ ಕಾಣುವುದಿಲ್ಲ: {reason}.",
        "ta": "{name} க்கு வரைவு தயாரிக்க மாட்டேன், ஏனெனில் விதிகளின்படி நீங்கள் தகுதி பெறவில்லை எனத் தெரிகிறது: {reason}.",
        "hinglish": "Main {name} ka draft nahi banaunga, kyonki niyamon ke hisaab se aap paatra nahi lagte: {reason}.",
    },
    "cancel_preview": {
        "en": "I can cancel your visit: {summary}. Nothing is cancelled yet. Press Confirm to cancel it.",
        "hi": "मैं आपकी यह मुलाकात रद्द कर सकता हूँ: {summary}। अभी कुछ रद्द नहीं हुआ है। रद्द करने के लिए 'पुष्टि करें' दबाएँ।",
        "kn": "ನಿಮ್ಮ ಈ ಭೇಟಿಯನ್ನು ರದ್ದುಮಾಡಬಹುದು: {summary}. ಇನ್ನೂ ಏನೂ ರದ್ದಾಗಿಲ್ಲ. ರದ್ದುಮಾಡಲು 'ದೃಢೀಕರಿಸಿ' ಒತ್ತಿ.",
        "ta": "உங்கள் வருகையை ரத்து செய்யலாம்: {summary}. இன்னும் எதுவும் ரத்து செய்யப்படவில்லை. ரத்து செய்ய 'உறுதிப்படுத்து' அழுத்தவும்.",
        "hinglish": "Main aapki yeh visit cancel kar sakta hoon: {summary}. Abhi kuch cancel nahi hua hai. Cancel karne ke liye Confirm dabaiye.",
    },
    "no_appointment": {
        "en": "You have no upcoming booked visit to cancel.", "hi": "रद्द करने के लिए आपकी कोई आने वाली बुक मुलाकात नहीं है।",
        "kn": "ರದ್ದುಮಾಡಲು ನಿಮ್ಮ ಯಾವುದೇ ಮುಂಬರುವ ಭೇಟಿ ಇಲ್ಲ.", "ta": "ரத்து செய்ய உங்களுக்கு வரவிருக்கும் முன்பதிவு எதுவும் இல்லை.",
        "hinglish": "Cancel karne ke liye aapki koi aane wali booked visit nahi hai.",
    },
    "reminder_preview": {
        "en": "I can set a reminder for {when}: \"{text}\". Nothing is set yet. Press Confirm to set it.",
        "hi": "मैं {when} के लिए याद दिलाना सेट कर सकता हूँ: \"{text}\"। अभी कुछ सेट नहीं हुआ है। सेट करने के लिए 'पुष्टि करें' दबाएँ।",
        "kn": "{when} ಕ್ಕೆ ಜ್ಞಾಪನೆ ಹೊಂದಿಸಬಹುದು: \"{text}\". ಇನ್ನೂ ಏನೂ ಹೊಂದಿಸಿಲ್ಲ. ಹೊಂದಿಸಲು 'ದೃಢೀಕರಿಸಿ' ಒತ್ತಿ.",
        "ta": "{when} க்கு நினைவூட்டல் அமைக்கலாம்: \"{text}\". இன்னும் எதுவும் அமைக்கப்படவில்லை. அமைக்க 'உறுதிப்படுத்து' அழுத்தவும்.",
        "hinglish": "Main {when} ke liye reminder set kar sakta hoon: \"{text}\". Abhi kuch set nahi hua hai. Set karne ke liye Confirm dabaiye.",
    },
    "reminder_text": {
        "en": "Last date for {name} is {date}.", "hi": "{name} की अंतिम तिथि {date} है।",
        "kn": "{name} ಕೊನೆಯ ದಿನಾಂಕ {date}.", "ta": "{name} கடைசி தேதி {date}.",
        "hinglish": "{name} ki aakhri tareekh {date} hai.",
    },
    "visit_reminder_text": {
        "en": "Visit {centre} at {slot}.", "hi": "{slot} पर {centre} जाना है।",
        "kn": "{slot} ಕ್ಕೆ {centre} ಭೇಟಿ.", "ta": "{slot} அன்று {centre} செல்ல வேண்டும்.",
        "hinglish": "{slot} par {centre} jaana hai.",
    },
    "no_deadline": {
        "en": "{name} has no last date, so a deadline reminder is not needed.",
        "hi": "{name} की कोई अंतिम तिथि नहीं है, इसलिए याद दिलाने की ज़रूरत नहीं है।",
        "kn": "{name} ಗೆ ಕೊನೆಯ ದಿನಾಂಕವಿಲ್ಲ, ಆದ್ದರಿಂದ ಜ್ಞಾಪನೆ ಅಗತ್ಯವಿಲ್ಲ.",
        "ta": "{name} க்குக் கடைசி தேதி இல்லை, எனவே நினைவூட்டல் தேவையில்லை.",
        "hinglish": "{name} ki koi aakhri tareekh nahi hai, isliye reminder ki zaroorat nahi hai.",
    },
    "confirm_typed": {
        "en": "To keep you safe, I only act when you press the Confirm button on the proposal. Nothing has been done yet.",
        "hi": "आपकी सुरक्षा के लिए, मैं तभी कुछ करता हूँ जब आप प्रस्ताव पर 'पुष्टि करें' बटन दबाते हैं। अभी कुछ नहीं किया गया है।",
        "kn": "ನಿಮ್ಮ ಸುರಕ್ಷತೆಗಾಗಿ, ನೀವು ಪ್ರಸ್ತಾವನೆಯ ಮೇಲಿನ 'ದೃಢೀಕರಿಸಿ' ಬಟನ್ ಒತ್ತಿದಾಗ ಮಾತ್ರ ಕ್ರಮ ಕೈಗೊಳ್ಳುತ್ತೇನೆ. ಇನ್ನೂ ಏನೂ ಮಾಡಿಲ್ಲ.",
        "ta": "உங்கள் பாதுகாப்பிற்காக, முன்மொழிவில் உள்ள 'உறுதிப்படுத்து' பொத்தானை அழுத்தும்போது மட்டுமே செயல்படுவேன். இன்னும் எதுவும் செய்யப்படவில்லை.",
        "hinglish": "Aapki suraksha ke liye, main tabhi kuch karta hoon jab aap proposal par Confirm button dabate hain. Abhi kuch nahi kiya gaya hai.",
    },
    "done_book": {
        "en": "Your visit is booked: {summary}. Booking ID: {id}.", "hi": "आपकी मुलाकात बुक हो गई है: {summary}। बुकिंग आईडी: {id}।",
        "kn": "ನಿಮ್ಮ ಭೇಟಿ ಬುಕ್ ಆಗಿದೆ: {summary}. ಬುಕಿಂಗ್ ಐಡಿ: {id}.", "ta": "உங்கள் வருகை முன்பதிவு செய்யப்பட்டது: {summary}. முன்பதிவு எண்: {id}.",
        "hinglish": "Aapki visit book ho gayi hai: {summary}. Booking ID: {id}.",
    },
    "done_reminder": {
        "en": "Reminder {id} is set for {when}.", "hi": "याद दिलाना {id}, {when} के लिए सेट है।",
        "kn": "ಜ್ಞಾಪನೆ {id}, {when} ಕ್ಕೆ ಹೊಂದಿಸಲಾಗಿದೆ.", "ta": "நினைவூட்டல் {id}, {when} க்கு அமைக்கப்பட்டது.",
        "hinglish": "Reminder {id}, {when} ke liye set hai.",
    },
    "done_draft": {
        "en": "Draft application {id} for {name} is ready. Status: draft. It has NOT been submitted. Take it with your documents to a service centre. The department makes the final decision.",
        "hi": "{name} के लिए ड्राफ़्ट आवेदन {id} तैयार है। स्थिति: ड्राफ़्ट। इसे जमा नहीं किया गया है। इसे दस्तावेज़ों के साथ सेवा केंद्र ले जाएँ। अंतिम निर्णय विभाग का होगा।",
        "kn": "{name} ಗಾಗಿ ಕರಡು ಅರ್ಜಿ {id} ಸಿದ್ಧವಾಗಿದೆ. ಸ್ಥಿತಿ: ಕರಡು. ಇದನ್ನು ಸಲ್ಲಿಸಲಾಗಿಲ್ಲ. ದಾಖಲೆಗಳೊಂದಿಗೆ ಸೇವಾ ಕೇಂದ್ರಕ್ಕೆ ತೆಗೆದುಕೊಂಡು ಹೋಗಿ. ಅಂತಿಮ ನಿರ್ಧಾರ ಇಲಾಖೆಯದ್ದು.",
        "ta": "{name} க்கான வரைவு விண்ணப்பம் {id} தயார். நிலை: வரைவு. இது சமர்ப்பிக்கப்படவில்லை. ஆவணங்களுடன் சேவை மையத்திற்குக் கொண்டு செல்லுங்கள். இறுதி முடிவை துறை எடுக்கும்.",
        "hinglish": "{name} ke liye draft aavedan {id} taiyaar hai. Status: draft. Ise jama nahi kiya gaya hai. Ise documents ke saath seva kendra le jaiye. Antim faisla vibhag ka hi hoga.",
    },
    "done_cancel": {
        "en": "Your visit {id} is cancelled.", "hi": "आपकी मुलाकात {id} रद्द कर दी गई है।",
        "kn": "ನಿಮ್ಮ ಭೇಟಿ {id} ರದ್ದಾಗಿದೆ.", "ta": "உங்கள் வருகை {id} ரத்து செய்யப்பட்டது.",
        "hinglish": "Aapki visit {id} cancel kar di gayi hai.",
    },
    "action_cancelled": {
        "en": "Okay, I have cancelled this proposal. Nothing was done.", "hi": "ठीक है, मैंने यह प्रस्ताव रद्द कर दिया है। कुछ नहीं किया गया।",
        "kn": "ಸರಿ, ಈ ಪ್ರಸ್ತಾವನೆಯನ್ನು ರದ್ದುಮಾಡಿದ್ದೇನೆ. ಏನೂ ಮಾಡಲಾಗಿಲ್ಲ.", "ta": "சரி, இந்த முன்மொழிவை ரத்து செய்தேன். எதுவும் செய்யப்படவில்லை.",
        "hinglish": "Theek hai, maine yeh proposal cancel kar diya hai. Kuch nahi kiya gaya.",
    },
    "need_login": {
        "en": "To do this I need to know who you are. Please sign in with your citizen ID (top of the screen) and ask again.",
        "hi": "इसके लिए मुझे जानना होगा कि आप कौन हैं। कृपया अपनी नागरिक आईडी से साइन इन करें (स्क्रीन के ऊपर) और फिर से पूछें।",
        "kn": "ಇದಕ್ಕಾಗಿ ನೀವು ಯಾರು ಎಂದು ತಿಳಿಯಬೇಕು. ದಯವಿಟ್ಟು ನಿಮ್ಮ ನಾಗರಿಕ ಐಡಿಯಿಂದ ಸೈನ್ ಇನ್ ಮಾಡಿ (ಪರದೆಯ ಮೇಲ್ಭಾಗ) ಮತ್ತು ಮತ್ತೆ ಕೇಳಿ.",
        "ta": "இதற்கு நீங்கள் யார் என்று தெரிய வேண்டும். உங்கள் குடிமக்கள் அடையாள எண்ணுடன் உள்நுழைந்து (திரையின் மேல்) மீண்டும் கேளுங்கள்.",
        "hinglish": "Iske liye mujhe jaanna hoga ki aap kaun hain. Kripya apni citizen ID se sign in karein (screen ke upar) aur phir se poochhiye.",
    },
    "need_consent": {
        "en": "I cannot use your saved profile because consent has not been given. I can still answer general questions, and you can tell me the details yourself.",
        "hi": "सहमति न होने के कारण मैं आपकी सहेजी गई प्रोफ़ाइल का उपयोग नहीं कर सकता। मैं सामान्य सवालों के जवाब दे सकता हूँ, और आप जानकारी ख़ुद बता सकते हैं।",
        "kn": "ಒಪ್ಪಿಗೆ ನೀಡದ ಕಾರಣ ನಿಮ್ಮ ಉಳಿಸಿದ ಪ್ರೊಫೈಲ್ ಬಳಸಲು ಸಾಧ್ಯವಿಲ್ಲ. ಸಾಮಾನ್ಯ ಪ್ರಶ್ನೆಗಳಿಗೆ ಉತ್ತರಿಸಬಲ್ಲೆ, ಮತ್ತು ನೀವೇ ವಿವರಗಳನ್ನು ತಿಳಿಸಬಹುದು.",
        "ta": "ஒப்புதல் தரப்படாததால் உங்கள் சேமித்த சுயவிவரத்தைப் பயன்படுத்த முடியாது. பொதுக் கேள்விகளுக்குப் பதிலளிக்க முடியும், விவரங்களை நீங்களே சொல்லலாம்.",
        "hinglish": "Sahmati na hone ki wajah se main aapki saved profile use nahi kar sakta. Main general sawaalon ke jawab de sakta hoon, aur aap jaankari khud bata sakte hain.",
    },
    "no_centre": {
        "en": "I could not find a service centre in {district}.", "hi": "{district} में कोई सेवा केंद्र नहीं मिला।",
        "kn": "{district} ನಲ್ಲಿ ಸೇವಾ ಕೇಂದ್ರ ಕಂಡುಬಂದಿಲ್ಲ.", "ta": "{district} இல் சேவை மையம் கிடைக்கவில்லை.",
        "hinglish": "{district} mein koi seva kendra nahi mila.",
    },
    "already_applied": {
        "en": "You already have an application for {name} (status: {status}, updated {date}), so I will not make another one.",
        "hi": "{name} के लिए आपका आवेदन पहले से है (स्थिति: {status}, {date} को अपडेट), इसलिए मैं नया नहीं बनाऊँगा।",
        "kn": "{name} ಗೆ ನಿಮ್ಮ ಅರ್ಜಿ ಈಗಾಗಲೇ ಇದೆ (ಸ್ಥಿತಿ: {status}, {date} ರಂದು ನವೀಕರಿಸಲಾಗಿದೆ), ಆದ್ದರಿಂದ ಇನ್ನೊಂದನ್ನು ಮಾಡುವುದಿಲ್ಲ.",
        "ta": "{name} க்கு உங்கள் விண்ணப்பம் ஏற்கனவே உள்ளது (நிலை: {status}, {date} அன்று புதுப்பிக்கப்பட்டது), எனவே இன்னொன்றை உருவாக்க மாட்டேன்.",
        "hinglish": "{name} ke liye aapka aavedan pehle se hai (status: {status}, {date} ko update), isliye main naya nahi banaunga.",
    },
    "rejected_note": {
        "en": "Your earlier application for {name} was rejected ({remarks}). If you disagree with this, I can send it to a grievance officer.",
        "hi": "{name} के लिए आपका पिछला आवेदन अस्वीकार हुआ था ({remarks})। अगर आप इससे असहमत हैं, तो मैं इसे शिकायत अधिकारी को भेज सकता हूँ।",
        "kn": "{name} ಗಾಗಿ ನಿಮ್ಮ ಹಿಂದಿನ ಅರ್ಜಿ ತಿರಸ್ಕೃತವಾಗಿತ್ತು ({remarks}). ನೀವು ಒಪ್ಪದಿದ್ದರೆ, ಕುಂದುಕೊರತೆ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಬಹುದು.",
        "ta": "{name} க்கான உங்கள் முந்தைய விண்ணப்பம் நிராகரிக்கப்பட்டது ({remarks}). நீங்கள் ஏற்கவில்லை என்றால், குறைதீர்ப்பு அலுவலருக்கு அனுப்ப முடியும்.",
        "hinglish": "{name} ke liye aapka pichhla aavedan reject hua tha ({remarks}). Agar aap isse sahmat nahi hain, to main ise shikayat officer ko bhej sakta hoon.",
    },
    # ------------------------------------------------------------------ referral / safety
    "ref_grievance": {
        "en": "I am sorry for the trouble you faced. {rule_line}I have sent your complaint, with full details, to the {queue}. They will contact you within {sla} working days. The final decision rests with the department.",
        "hi": "आपको जो परेशानी हुई, उसके लिए मुझे खेद है। {rule_line}मैंने आपकी शिकायत पूरे विवरण के साथ {queue} को भेज दी है। वे {sla} कार्य दिवसों के अंदर आपसे संपर्क करेंगे। अंतिम निर्णय विभाग का ही होगा।",
        "kn": "ನಿಮಗಾದ ತೊಂದರೆಗೆ ವಿಷಾದಿಸುತ್ತೇನೆ. {rule_line}ನಿಮ್ಮ ದೂರನ್ನು ಸಂಪೂರ್ಣ ವಿವರಗಳೊಂದಿಗೆ {queue} ಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ. ಅವರು {sla} ಕೆಲಸದ ದಿನಗಳೊಳಗೆ ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತಾರೆ. ಅಂತಿಮ ನಿರ್ಧಾರ ಇಲಾಖೆಯದ್ದೇ.",
        "ta": "உங்களுக்கு ஏற்பட்ட சிரமத்திற்கு வருந்துகிறேன். {rule_line}உங்கள் புகாரை முழு விவரங்களுடன் {queue} க்கு அனுப்பியுள்ளேன். அவர்கள் {sla} வேலை நாட்களுக்குள் உங்களைத் தொடர்புகொள்வார்கள். இறுதி முடிவு துறையுடையதே.",
        "hinglish": "Aapko jo pareshani hui, uska mujhe khed hai. {rule_line}Maine aapki shikayat poore vivaran ke saath {queue} ko bhej di hai. Woh {sla} kaam ke din ke andar aapse sampark karenge. Is par antim faisla vibhag ka hi hoga.",
    },
    "bribe_rule_line": {
        "en": "Asking for money in return for work is against the rules (POL-FEE-01). ",
        "hi": "काम के बदले पैसे माँगना नियम के ख़िलाफ़ है (POL-FEE-01)। ",
        "kn": "ಕೆಲಸಕ್ಕೆ ಬದಲಾಗಿ ಹಣ ಕೇಳುವುದು ನಿಯಮಬಾಹಿರ (POL-FEE-01). ",
        "ta": "வேலைக்குப் பணம் கேட்பது விதிகளுக்கு எதிரானது (POL-FEE-01). ",
        "hinglish": "Kaam ke badle paise maangna niyam ke khilaaf hai (POL-FEE-01). ",
    },
    "ref_fraud": {
        "en": "Please do not pay. No scheme charges any fee, and there is no \"release fee\" for scheme money (POL-FEE-01). Never share your OTP, bank PIN or account number with anyone on a call. I have reported this to the {queue}; they will contact you within {sla} working days. If you have already paid or shared an OTP, call your bank at once.",
        "hi": "कृपया कोई पैसा न दें। किसी भी योजना में कोई शुल्क नहीं लगता, और योजना का पैसा \"रिलीज़\" करने की कोई फ़ीस नहीं होती (POL-FEE-01)। अपना OTP, बैंक PIN या खाता नंबर फ़ोन पर किसी को न बताएँ। मैंने इसकी सूचना {queue} को दे दी है; वे {sla} कार्य दिवसों में आपसे संपर्क करेंगे। अगर आपने पैसे दे दिए हैं या OTP बता दिया है, तो तुरंत अपने बैंक को फ़ोन करें।",
        "kn": "ದಯವಿಟ್ಟು ಹಣ ಪಾವತಿಸಬೇಡಿ. ಯಾವುದೇ ಯೋಜನೆಗೆ ಶುಲ್ಕವಿಲ್ಲ, ಯೋಜನೆಯ ಹಣ \"ಬಿಡುಗಡೆ\"ಗೆ ಯಾವುದೇ ಶುಲ್ಕವಿಲ್ಲ (POL-FEE-01). ನಿಮ್ಮ OTP, ಬ್ಯಾಂಕ್ PIN ಅಥವಾ ಖಾತೆ ಸಂಖ್ಯೆಯನ್ನು ಕರೆಯಲ್ಲಿ ಯಾರಿಗೂ ಹೇಳಬೇಡಿ. ಇದನ್ನು {queue} ಗೆ ವರದಿ ಮಾಡಿದ್ದೇನೆ; ಅವರು {sla} ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ಸಂಪರ್ಕಿಸುತ್ತಾರೆ. ಈಗಾಗಲೇ ಹಣ ಕೊಟ್ಟಿದ್ದರೆ ಅಥವಾ OTP ಹೇಳಿದ್ದರೆ, ತಕ್ಷಣ ನಿಮ್ಮ ಬ್ಯಾಂಕ್‌ಗೆ ಕರೆ ಮಾಡಿ.",
        "ta": "தயவுசெய்து பணம் செலுத்த வேண்டாம். எந்தத் திட்டத்திற்கும் கட்டணம் இல்லை, திட்டப் பணத்தை \"விடுவிக்க\" எந்தக் கட்டணமும் இல்லை (POL-FEE-01). உங்கள் OTP, வங்கி PIN அல்லது கணக்கு எண்ணை அழைப்பில் யாரிடமும் சொல்ல வேண்டாம். இதை {queue} க்குத் தெரிவித்துள்ளேன்; அவர்கள் {sla} வேலை நாட்களுக்குள் தொடர்புகொள்வார்கள். ஏற்கனவே பணம் கொடுத்திருந்தால் அல்லது OTP சொல்லியிருந்தால், உடனே உங்கள் வங்கியை அழைக்கவும்.",
        "hinglish": "Kripya koi paisa na dein. Kisi bhi scheme mein koi fees nahi lagti, aur scheme ka paisa \"release\" karne ki koi fees nahi hoti (POL-FEE-01). Apna OTP, bank PIN ya account number phone par kisi ko na batayein. Maine iski jaankari {queue} ko de di hai; woh {sla} kaam ke din mein aapse sampark karenge. Agar aapne paise de diye hain ya OTP bata diya hai, to turant apne bank ko phone karein.",
    },
    "ref_generic": {
        "en": "I have passed your question, with all the details, to the {queue}. An officer will contact you within {sla} working days. I cannot promise an outcome; the department decides.",
        "hi": "मैंने आपका सवाल पूरे विवरण के साथ {queue} को भेज दिया है। एक अधिकारी {sla} कार्य दिवसों में आपसे संपर्क करेंगे। मैं किसी नतीजे का वादा नहीं कर सकता; निर्णय विभाग का होगा।",
        "kn": "ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಎಲ್ಲ ವಿವರಗಳೊಂದಿಗೆ {queue} ಗೆ ಕಳುಹಿಸಿದ್ದೇನೆ. ಒಬ್ಬ ಅಧಿಕಾರಿ {sla} ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ನಿಮ್ಮನ್ನು ಸಂಪರ್ಕಿಸುತ್ತಾರೆ. ಫಲಿತಾಂಶದ ಭರವಸೆ ನೀಡಲಾರೆ; ಇಲಾಖೆ ನಿರ್ಧರಿಸುತ್ತದೆ.",
        "ta": "உங்கள் கேள்வியை அனைத்து விவரங்களுடன் {queue} க்கு அனுப்பியுள்ளேன். ஒரு அலுவலர் {sla} வேலை நாட்களுக்குள் உங்களைத் தொடர்புகொள்வார். முடிவுக்கு நான் உறுதியளிக்க முடியாது; துறையே முடிவு செய்யும்.",
        "hinglish": "Maine aapka sawaal poore vivaran ke saath {queue} ko bhej diya hai. Ek officer {sla} kaam ke din mein aapse sampark karenge. Main kisi nateeje ka vaada nahi kar sakta; faisla vibhag ka hoga.",
    },
    "ref_human": {
        "en": "Sure. I have asked an officer from the {queue} to help you. They will contact you within {sla} working days. The final decision rests with the department.",
        "hi": "ज़रूर। मैंने {queue} के एक अधिकारी से आपकी मदद करने को कहा है। वे {sla} कार्य दिवसों में आपसे संपर्क करेंगे। अंतिम निर्णय विभाग का ही होगा।",
        "kn": "ಖಂಡಿತ. ನಿಮಗೆ ಸಹಾಯ ಮಾಡಲು {queue} ಅಧಿಕಾರಿಯನ್ನು ಕೇಳಿದ್ದೇನೆ. ಅವರು {sla} ಕೆಲಸದ ದಿನಗಳಲ್ಲಿ ಸಂಪರ್ಕಿಸುತ್ತಾರೆ. ಅಂತಿಮ ನಿರ್ಧಾರ ಇಲಾಖೆಯದ್ದೇ.",
        "ta": "நிச்சயமாக. உங்களுக்கு உதவ {queue} அலுவலரைக் கேட்டுள்ளேன். அவர்கள் {sla} வேலை நாட்களுக்குள் தொடர்புகொள்வார்கள். இறுதி முடிவு துறையுடையதே.",
        "hinglish": "Zaroor. Maine {queue} ke ek officer se aapki madad karne ko kaha hai. Woh {sla} kaam ke din mein aapse sampark karenge. Antim faisla vibhag ka hi hoga.",
    },
    "ref_id_line": {
        "en": "Reference number: {rid}", "hi": "संदर्भ संख्या: {rid}", "kn": "ಉಲ್ಲೇಖ ಸಂಖ್ಯೆ: {rid}",
        "ta": "குறிப்பு எண்: {rid}", "hinglish": "Reference number: {rid}",
    },
    "q_grievance": {"en": "grievance department", "hi": "शिकायत विभाग", "kn": "ಕುಂದುಕೊರತೆ ವಿಭಾಗ", "ta": "குறைதீர்ப்புத் துறை", "hinglish": "shikayat vibhag"},
    "q_fraud_desk": {"en": "fraud desk", "hi": "धोखाधड़ी शिकायत डेस्क", "kn": "ವಂಚನೆ ದೂರು ವಿಭಾಗ", "ta": "மோசடி புகார் பிரிவு", "hinglish": "fraud desk"},
    "q_department_helpdesk": {"en": "department helpdesk", "hi": "विभाग की हेल्पडेस्क", "kn": "ಇಲಾಖೆಯ ಸಹಾಯವಾಣಿ", "ta": "துறை உதவி மையம்", "hinglish": "vibhag helpdesk"},
    "not_found": {
        "en": "I could not find this in the Mitrapur Pradesh scheme documents I have, so I will not guess. If you want, I can pass your question to the department helpdesk.",
        "hi": "मेरे पास मौजूद मित्रपुर प्रदेश की योजनाओं के दस्तावेज़ों में यह जानकारी नहीं है, इसलिए मैं अंदाज़ा नहीं लगाऊँगा। आप चाहें तो मैं आपका सवाल विभाग की हेल्पडेस्क को भेज सकता हूँ।",
        "kn": "ನನ್ನ ಬಳಿ ಇರುವ ಮಿತ್ರಪುರ ಪ್ರದೇಶದ ಯೋಜನಾ ದಾಖಲೆಗಳಲ್ಲಿ ಈ ಮಾಹಿತಿ ಇಲ್ಲ, ಆದ್ದರಿಂದ ನಾನು ಊಹಿಸುವುದಿಲ್ಲ. ನೀವು ಬಯಸಿದರೆ, ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಇಲಾಖೆಯ ಸಹಾಯವಾಣಿಗೆ ಕಳುಹಿಸಬಹುದು.",
        "ta": "என்னிடம் உள்ள மித்ரபூர் பிரதேச திட்ட ஆவணங்களில் இந்தத் தகவல் இல்லை, எனவே நான் ஊகிக்க மாட்டேன். நீங்கள் விரும்பினால், உங்கள் கேள்வியை துறை உதவி மையத்திற்கு அனுப்ப முடியும்.",
        "hinglish": "Mere paas Mitrapur Pradesh ki schemes ke documents mein yeh jaankari nahi hai, isliye main andaaza nahi lagaunga. Aap chahein to main aapka sawaal vibhag helpdesk ko bhej sakta hoon.",
    },
    "out_of_scope": {
        "en": "I can only help with Mitrapur Pradesh welfare schemes: finding schemes, checking eligibility, documents, last dates, and booking a service-centre visit.",
        "hi": "मैं सिर्फ़ मित्रपुर प्रदेश की कल्याण योजनाओं में मदद कर सकता हूँ: योजनाएँ ढूँढना, पात्रता जाँचना, दस्तावेज़, अंतिम तिथि, और सेवा केंद्र पर मुलाकात बुक करना।",
        "kn": "ನಾನು ಮಿತ್ರಪುರ ಪ್ರದೇಶದ ಕಲ್ಯಾಣ ಯೋಜನೆಗಳ ಬಗ್ಗೆ ಮಾತ್ರ ಸಹಾಯ ಮಾಡಬಲ್ಲೆ: ಯೋಜನೆಗಳನ್ನು ಹುಡುಕುವುದು, ಅರ್ಹತೆ ಪರಿಶೀಲನೆ, ದಾಖಲೆಗಳು, ಕೊನೆಯ ದಿನಾಂಕ ಮತ್ತು ಸೇವಾ ಕೇಂದ್ರ ಭೇಟಿ ಬುಕ್ ಮಾಡುವುದು.",
        "ta": "மித்ரபூர் பிரதேச நலத் திட்டங்களில் மட்டுமே என்னால் உதவ முடியும்: திட்டங்களைக் கண்டறிதல், தகுதி சரிபார்த்தல், ஆவணங்கள், கடைசி தேதி, சேவை மைய வருகை முன்பதிவு.",
        "hinglish": "Main sirf Mitrapur Pradesh ki kalyan schemes mein madad kar sakta hoon: schemes dhoondhna, eligibility check, documents, aakhri tareekh, aur seva kendra visit book karna.",
    },
    "refused_other": {
        "en": "I cannot share or look up details about another person. I can only use your own profile, and only with your consent.",
        "hi": "मैं किसी दूसरे व्यक्ति की जानकारी न तो बता सकता हूँ, न खोज सकता हूँ। मैं सिर्फ़ आपकी अपनी प्रोफ़ाइल, आपकी सहमति से, इस्तेमाल कर सकता हूँ।",
        "kn": "ಇನ್ನೊಬ್ಬ ವ್ಯಕ್ತಿಯ ವಿವರಗಳನ್ನು ನಾನು ಹಂಚಿಕೊಳ್ಳಲು ಅಥವಾ ಹುಡುಕಲು ಸಾಧ್ಯವಿಲ್ಲ. ನಿಮ್ಮ ಸ್ವಂತ ಪ್ರೊಫೈಲ್ ಅನ್ನು ಮಾತ್ರ, ನಿಮ್ಮ ಒಪ್ಪಿಗೆಯೊಂದಿಗೆ ಬಳಸಬಹುದು.",
        "ta": "மற்றொருவரின் விவரங்களைப் பகிரவோ தேடவோ என்னால் முடியாது. உங்கள் சொந்த சுயவிவரத்தை மட்டுமே, உங்கள் ஒப்புதலுடன் பயன்படுத்த முடியும்.",
        "hinglish": "Main kisi doosre vyakti ki jaankari na bata sakta hoon, na dhoondh sakta hoon. Main sirf aapki apni profile, aapki sahmati se, use kar sakta hoon.",
    },
    "refused_secret": {
        "en": "I cannot share internal instructions, system settings or secrets.",
        "hi": "मैं अंदरूनी निर्देश, सिस्टम सेटिंग या गोपनीय जानकारी साझा नहीं कर सकता।",
        "kn": "ಆಂತರಿಕ ಸೂಚನೆಗಳು, ಸಿಸ್ಟಮ್ ಸೆಟ್ಟಿಂಗ್‌ಗಳು ಅಥವಾ ರಹಸ್ಯಗಳನ್ನು ಹಂಚಿಕೊಳ್ಳಲು ಸಾಧ್ಯವಿಲ್ಲ.",
        "ta": "உள் வழிமுறைகள், அமைப்பு அமைப்புகள் அல்லது ரகசியங்களைப் பகிர முடியாது.",
        "hinglish": "Main andar ke instructions, system settings ya secrets share nahi kar sakta.",
    },
    "pii_warning": {
        "en": "For your safety, please do not share OTPs, bank account numbers or ID numbers here. I have hidden them.",
        "hi": "आपकी सुरक्षा के लिए, कृपया यहाँ OTP, बैंक खाता नंबर या पहचान संख्या न लिखें। मैंने उन्हें छिपा दिया है।",
        "kn": "ನಿಮ್ಮ ಸುರಕ್ಷತೆಗಾಗಿ, ದಯವಿಟ್ಟು ಇಲ್ಲಿ OTP, ಬ್ಯಾಂಕ್ ಖಾತೆ ಸಂಖ್ಯೆ ಅಥವಾ ಗುರುತಿನ ಸಂಖ್ಯೆಯನ್ನು ಹಂಚಿಕೊಳ್ಳಬೇಡಿ. ನಾನು ಅವುಗಳನ್ನು ಮರೆಮಾಡಿದ್ದೇನೆ.",
        "ta": "உங்கள் பாதுகாப்பிற்காக, தயவுசெய்து இங்கே OTP, வங்கிக் கணக்கு எண் அல்லது அடையாள எண்ணைப் பகிர வேண்டாம். அவற்றை மறைத்துவிட்டேன்.",
        "hinglish": "Aapki suraksha ke liye, kripya yahan OTP, bank account number ya ID number na likhein. Maine unhe chhupa diya hai.",
    },
    "injection_note": {
        "en": "I cannot change scheme rules or mark anyone eligible. Eligibility is checked only against the published rules. Tell me about the person who wants to apply and I will check.",
        "hi": "मैं योजना के नियम नहीं बदल सकता और न ही किसी को पात्र घोषित कर सकता हूँ। पात्रता सिर्फ़ प्रकाशित नियमों से जाँची जाती है। आवेदन करने वाले के बारे में बताइए, मैं जाँच करूँगा।",
        "kn": "ನಾನು ಯೋಜನೆಯ ನಿಯಮಗಳನ್ನು ಬದಲಿಸಲು ಅಥವಾ ಯಾರನ್ನೂ ಅರ್ಹರೆಂದು ಘೋಷಿಸಲು ಸಾಧ್ಯವಿಲ್ಲ. ಅರ್ಹತೆಯನ್ನು ಪ್ರಕಟಿತ ನಿಯಮಗಳ ಆಧಾರದಲ್ಲಿ ಮಾತ್ರ ಪರಿಶೀಲಿಸಲಾಗುತ್ತದೆ. ಅರ್ಜಿ ಸಲ್ಲಿಸುವವರ ಬಗ್ಗೆ ತಿಳಿಸಿ, ನಾನು ಪರಿಶೀಲಿಸುತ್ತೇನೆ.",
        "ta": "திட்ட விதிகளை மாற்றவோ யாரையும் தகுதியானவர் என அறிவிக்கவோ என்னால் முடியாது. வெளியிடப்பட்ட விதிகளின்படி மட்டுமே தகுதி சரிபார்க்கப்படும். விண்ணப்பிப்பவர் பற்றிச் சொல்லுங்கள், நான் சரிபார்க்கிறேன்.",
        "hinglish": "Main scheme ke niyam nahi badal sakta aur na hi kisi ko paatra bana sakta hoon. Eligibility sirf published niyamon se check hoti hai. Aavedan karne wale ke baare mein bataiye, main check karunga.",
    },
    "greeting": {
        "en": "Namaste! I am SchemeSathi. I can help you find Mitrapur Pradesh schemes, check eligibility, list documents, check last dates and book a service-centre visit. What would you like to know?",
        "hi": "नमस्ते! मैं स्कीमसाथी हूँ। मैं मित्रपुर प्रदेश की योजनाएँ ढूँढने, पात्रता जाँचने, दस्तावेज़ बताने, अंतिम तिथि देखने और सेवा केंद्र पर मुलाकात बुक करने में मदद कर सकता हूँ। आप क्या जानना चाहते हैं?",
        "kn": "ನಮಸ್ಕಾರ! ನಾನು ಸ್ಕೀಮ್‌ಸಾಥಿ. ಮಿತ್ರಪುರ ಪ್ರದೇಶದ ಯೋಜನೆಗಳನ್ನು ಹುಡುಕಲು, ಅರ್ಹತೆ ಪರಿಶೀಲಿಸಲು, ದಾಖಲೆಗಳನ್ನು ತಿಳಿಸಲು, ಕೊನೆಯ ದಿನಾಂಕ ನೋಡಲು ಮತ್ತು ಸೇವಾ ಕೇಂದ್ರ ಭೇಟಿ ಬುಕ್ ಮಾಡಲು ಸಹಾಯ ಮಾಡಬಲ್ಲೆ. ನೀವು ಏನು ತಿಳಿಯಲು ಬಯಸುತ್ತೀರಿ?",
        "ta": "வணக்கம்! நான் ஸ்கீம்சாத்தி. மித்ரபூர் பிரதேச திட்டங்களைக் கண்டறிய, தகுதியைச் சரிபார்க்க, ஆவணங்களைச் சொல்ல, கடைசி தேதியைப் பார்க்க, சேவை மைய வருகையை முன்பதிவு செய்ய உதவ முடியும். நீங்கள் என்ன தெரிந்துகொள்ள விரும்புகிறீர்கள்?",
        "hinglish": "Namaste! Main SchemeSathi hoon. Main Mitrapur Pradesh ki schemes dhoondhne, eligibility check karne, documents batane, aakhri tareekh dekhne aur seva kendra visit book karne mein madad kar sakta hoon. Aap kya jaanna chahte hain?",
    },
    "source_label": {"en": "Source", "hi": "स्रोत", "kn": "ಮೂಲ", "ta": "ஆதாரம்", "hinglish": "Source"},
    "section_label": {"en": "Section", "hi": "धारा", "kn": "ವಿಭಾಗ", "ta": "பிரிவு", "hinglish": "Section"},
}

ATTR_LABEL: dict[str, dict[str, str]] = {
    "age": {"en": "age", "hi": "आयु", "kn": "ವಯಸ್ಸು", "ta": "வயது", "hinglish": "umar"},
    "annual_household_income": {"en": "yearly household income", "hi": "परिवार की सालाना आय", "kn": "ಕುಟುಂಬದ ವಾರ್ಷಿಕ ಆದಾಯ", "ta": "குடும்பத்தின் ஆண்டு வருமானம்", "hinglish": "parivaar ki saalana aamdani"},
    "land_holding_acres": {"en": "land holding", "hi": "ज़मीन", "kn": "ಜಮೀನು", "ta": "நிலம்", "hinglish": "zameen"},
    "gender": {"en": "gender", "hi": "लिंग", "kn": "ಲಿಂಗ", "ta": "பாலினம்", "hinglish": "ling"},
    "category": {"en": "social category", "hi": "सामाजिक वर्ग", "kn": "ಸಾಮಾಜಿಕ ವರ್ಗ", "ta": "சமூகப் பிரிவு", "hinglish": "varg (category)"},
    "district": {"en": "district", "hi": "ज़िला", "kn": "ಜಿಲ್ಲೆ", "ta": "மாவட்டம்", "hinglish": "zila"},
    "residence_type": {"en": "lives in", "hi": "निवास", "kn": "ವಾಸ", "ta": "வசிப்பிடம்", "hinglish": "rehte hain"},
    "is_disabled": {"en": "disability", "hi": "दिव्यांगता", "kn": "ಅಂಗವೈಕಲ್ಯ", "ta": "மாற்றுத்திறன்", "hinglish": "divyangta"},
    "disability_percent": {"en": "disability percentage", "hi": "दिव्यांगता प्रतिशत", "kn": "ಅಂಗವೈಕಲ್ಯ ಶೇಕಡಾ", "ta": "மாற்றுத்திறன் சதவீதம்", "hinglish": "divyangta pratishat"},
    "occupation": {"en": "occupation", "hi": "काम / व्यवसाय", "kn": "ಉದ್ಯೋಗ", "ta": "தொழில்", "hinglish": "kaam"},
}

OP_PHRASE: dict[str, dict[str, str]] = {
    ">=": {"en": "{attr} must be at least {v}", "hi": "{attr} कम से कम {v} होनी चाहिए", "kn": "{attr} ಕನಿಷ್ಠ {v} ಇರಬೇಕು", "ta": "{attr} குறைந்தது {v} ஆக இருக்க வேண்டும்", "hinglish": "{attr} kam se kam {v} honi chahiye"},
    "<=": {"en": "{attr} must be at most {v}", "hi": "{attr} अधिकतम {v} होनी चाहिए", "kn": "{attr} ಗರಿಷ್ಠ {v} ಇರಬೇಕು", "ta": "{attr} அதிகபட்சம் {v} ஆக இருக்க வேண்டும்", "hinglish": "{attr} zyada se zyada {v} honi chahiye"},
    "=": {"en": "{attr} must be {v}", "hi": "{attr} {v} होना चाहिए", "kn": "{attr} {v} ಆಗಿರಬೇಕು", "ta": "{attr} {v} ஆக இருக்க வேண்டும்", "hinglish": "{attr} {v} hona chahiye"},
    "!=": {"en": "{attr} must not be {v}", "hi": "{attr} {v} नहीं होना चाहिए", "kn": "{attr} {v} ಆಗಿರಬಾರದು", "ta": "{attr} {v} ஆக இருக்கக் கூடாது", "hinglish": "{attr} {v} nahi hona chahiye"},
    "in": {"en": "{attr} must be one of: {v}", "hi": "{attr} इनमें से एक होना चाहिए: {v}", "kn": "{attr} ಇವುಗಳಲ್ಲಿ ಒಂದಾಗಿರಬೇಕು: {v}", "ta": "{attr} இவற்றில் ஒன்றாக இருக்க வேண்டும்: {v}", "hinglish": "{attr} inmein se ek hona chahiye: {v}"},
    "not_in": {"en": "{attr} must not be: {v}", "hi": "{attr} इनमें से नहीं होना चाहिए: {v}", "kn": "{attr} ಇವುಗಳಲ್ಲಿ ಒಂದಾಗಿರಬಾರದು: {v}", "ta": "{attr} இவற்றில் ஒன்றாக இருக்கக் கூடாது: {v}", "hinglish": "{attr} inmein se nahi hona chahiye: {v}"},
}

VALUE_LABEL: dict[str, dict[str, str]] = {
    "female": {"en": "female", "hi": "महिला", "kn": "ಮಹಿಳೆ", "ta": "பெண்", "hinglish": "mahila"},
    "male": {"en": "male", "hi": "पुरुष", "kn": "ಪುರುಷ", "ta": "ஆண்", "hinglish": "purush"},
    "other": {"en": "other", "hi": "अन्य", "kn": "ಇತರ", "ta": "பிற", "hinglish": "anya"},
    "rural": {"en": "rural (village)", "hi": "ग्रामीण (गाँव)", "kn": "ಗ್ರಾಮೀಣ (ಹಳ್ಳಿ)", "ta": "கிராமப்புறம்", "hinglish": "gaon (rural)"},
    "urban": {"en": "urban (town/city)", "hi": "शहरी", "kn": "ನಗರ", "ta": "நகர்ப்புறம்", "hinglish": "shahar (urban)"},
    "farmer": {"en": "farmer", "hi": "किसान", "kn": "ರೈತ", "ta": "விவசாயி", "hinglish": "kisan"},
    "student": {"en": "student", "hi": "विद्यार्थी", "kn": "ವಿದ್ಯಾರ್ಥಿ", "ta": "மாணவர்", "hinglish": "student"},
    "daily_wage": {"en": "daily-wage worker", "hi": "दिहाड़ी मज़दूर", "kn": "ಕೂಲಿ ಕಾರ್ಮಿಕ", "ta": "கூலித் தொழிலாளி", "hinglish": "dihadi mazdoor"},
    "construction_worker": {"en": "construction worker", "hi": "निर्माण मज़दूर", "kn": "ಕಟ್ಟಡ ಕಾರ್ಮಿಕ", "ta": "கட்டுமானத் தொழிலாளி", "hinglish": "construction mazdoor"},
    "street_vendor": {"en": "street vendor", "hi": "रेहड़ी-पटरी विक्रेता", "kn": "ಬೀದಿ ವ್ಯಾಪಾರಿ", "ta": "தெரு வியாபாரி", "hinglish": "rehri wala"},
    "homemaker": {"en": "homemaker", "hi": "गृहिणी", "kn": "ಗೃಹಿಣಿ", "ta": "இல்லத்தரசி", "hinglish": "grihini"},
    "retired": {"en": "retired", "hi": "सेवानिवृत्त", "kn": "ನಿವೃತ್ತ", "ta": "ஓய்வு பெற்றவர்", "hinglish": "retired"},
    "salaried": {"en": "salaried", "hi": "वेतनभोगी", "kn": "ಸಂಬಳದ ಉದ್ಯೋಗಿ", "ta": "சம்பளம் பெறுபவர்", "hinglish": "naukri"},
    "self_employed": {"en": "self-employed", "hi": "स्वरोज़गार", "kn": "ಸ್ವಉದ್ಯೋಗಿ", "ta": "சுயதொழில்", "hinglish": "apna kaam"},
    "unemployed": {"en": "unemployed", "hi": "बेरोज़गार", "kn": "ನಿರುದ್ಯೋಗಿ", "ta": "வேலையில்லாதவர்", "hinglish": "berozgar"},
    "Y": {"en": "yes", "hi": "हाँ", "kn": "ಹೌದು", "ta": "ஆம்", "hinglish": "haan"},
    "N": {"en": "no", "hi": "नहीं", "kn": "ಇಲ್ಲ", "ta": "இல்லை", "hinglish": "nahi"},
}

UNIT: dict[str, dict[str, str]] = {
    "years": {"en": "years", "hi": "वर्ष", "kn": "ವರ್ಷ", "ta": "வயது", "hinglish": "saal"},
    "acres": {"en": "acres", "hi": "एकड़", "kn": "ಎಕರೆ", "ta": "ஏக்கர்", "hinglish": "acre"},
}

WEEKDAYS: dict[str, list[str]] = {
    "en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
    "kn": ["ಸೋಮವಾರ", "ಮಂಗಳವಾರ", "ಬುಧವಾರ", "ಗುರುವಾರ", "ಶುಕ್ರವಾರ", "ಶನಿವಾರ", "ಭಾನುವಾರ"],
    "ta": ["திங்கள்", "செவ்வாய்", "புதன்", "வியாழன்", "வெள்ளி", "சனி", "ஞாயிறு"],
    "hinglish": ["Somvaar", "Mangalvaar", "Budhvaar", "Guruvaar", "Shukravaar", "Shanivaar", "Ravivaar"],
}
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def L(lang: str) -> str:
    return lang if lang in LANGS else "en"


def t(key: str, lang: str, **kw: Any) -> str:
    entry = T[key]
    template = entry.get(L(lang)) or entry["en"]
    return template.format(**kw) if kw else template


def inr(amount: Any) -> str:
    """Indian digit grouping: 120000 -> ₹1,20,000. Identical in every language."""
    try:
        n = int(round(float(amount)))
    except (TypeError, ValueError):
        return str(amount)
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups) + "," + tail
    return ("-" if n < 0 else "") + "₹" + s


def fmt_date(d: str | date | None) -> str:
    """DD-MM-YYYY: numeric and therefore identical across languages."""
    if not d:
        return ""
    if isinstance(d, str):
        d = date.fromisoformat(d[:10])
    return d.strftime("%d-%m-%Y")


def fmt_slot(dt: datetime, lang: str) -> str:
    wd = WEEKDAYS[L(lang)][dt.weekday()]
    return f"{fmt_date(dt.date())} ({wd}), {dt.strftime('%H:%M')}"


def fmt_slot_en(dt: datetime) -> str:
    return f"{WEEKDAYS['en'][dt.weekday()]} {dt.day} {MONTHS_EN[dt.month - 1]} {dt.year}, {dt.strftime('%H:%M')}"


def attr_label(attr: str, lang: str) -> str:
    return ATTR_LABEL.get(attr, {}).get(L(lang), attr.replace("_", " "))


def value_label(attr: str, value: Any, lang: str) -> str:
    if value is None or value == "":
        return "?"
    if attr == "annual_household_income":
        return inr(value)
    if attr == "land_holding_acres":
        v = float(value)
        return f"{v:g} {UNIT['acres'][L(lang)]}"
    if attr == "age":
        return f"{int(float(value))} {UNIT['years'][L(lang)]}"
    if attr == "disability_percent":
        return f"{int(float(value))}%"
    if attr == "category":
        return str(value).upper()
    if isinstance(value, str) and ";" in value:
        return ", ".join(value_label(attr, v, lang) for v in value.split(";"))
    sval = str(value)
    if sval in VALUE_LABEL:
        return VALUE_LABEL[sval][L(lang)]
    if sval.lower() in VALUE_LABEL:
        return VALUE_LABEL[sval.lower()][L(lang)]
    return sval


def rule_phrase(attr: str, op: str, value: Any, lang: str) -> str:
    tmpl = OP_PHRASE.get(op, OP_PHRASE["="])[L(lang)]
    return tmpl.format(attr=attr_label(attr, lang), v=value_label(attr, value, lang))


def scheme_name(scheme: dict[str, Any] | None, lang: str, both: bool = True) -> str:
    """Scheme name in the citizen's script plus English (R6)."""
    if not scheme:
        return ""
    en = scheme.get("name_en") or scheme.get("scheme_id", "")
    local = {"hi": scheme.get("name_hi"), "kn": scheme.get("name_kn"), "ta": scheme.get("name_ta")}.get(lang)
    if lang == "hinglish":
        return en
    if local and local != en:
        return f"{local} ({en})" if both else local
    return en


def benefit_text(scheme: dict[str, Any], lang: str) -> str:
    key = {"hi": "benefit_summary_hi", "kn": "benefit_summary_kn", "ta": "benefit_summary_ta"}.get(lang)
    return (scheme.get(key) if key else None) or scheme.get("benefit_summary") or ""


def doc_name(doc: dict[str, Any], lang: str) -> str:
    key = {"hi": "document_name_hi", "kn": "document_name_kn", "ta": "document_name_ta"}.get(lang)
    return (doc.get(key) if key else None) or doc.get("document_name", "")


def citation_label(source_id: str, section: str, lang: str) -> str:
    sec_no = (section or "").split(" ")[0]
    if sec_no:
        return f"{t('source_label', lang)}: {source_id}, {t('section_label', lang)} {sec_no}"
    return f"{t('source_label', lang)}: {source_id}"


def join_list(items: list[str], lang: str) -> str:
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + t("or", lang).replace(" or ", " and ").replace(" या ", " और ").replace(" ಅಥವಾ ", " ಮತ್ತು ").replace(" அல்லது ", " மற்றும் ").replace(" ya ", " aur ") + items[-1]
