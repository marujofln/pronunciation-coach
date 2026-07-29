from sqlmodel import Session, select

from app.models import Difficulty, Phrase

# Grouped by category rather than by difficulty: every category must offer at
# least one phrase at each difficulty (otherwise that filter combination 404s
# from /api/phrases/random), and that is only checkable at a glance if a
# category's phrases sit together.
PHRASES: list[dict] = [
    # ============================ everyday conversation ============================
    # --- greetings ---
    {
        "text": "Good morning, how are you today?",
        "difficulty": Difficulty.easy,
        "category": "greetings",
    },
    {
        "text": "Hello, my name is Alex.",
        "difficulty": Difficulty.easy,
        "category": "greetings",
    },
    {
        "text": "Nice to meet you.",
        "difficulty": Difficulty.easy,
        "category": "greetings",
    },
    {
        "text": "It is a pleasure to finally meet you in person.",
        "difficulty": Difficulty.medium,
        "category": "greetings",
    },
    {
        "text": "Allow me to introduce my distinguished colleague from the Edinburgh office.",
        "difficulty": Difficulty.hard,
        "category": "greetings",
    },
    # --- small-talk ---
    {
        "text": "What time is it now?",
        "difficulty": Difficulty.easy,
        "category": "small-talk",
    },
    {
        "text": "Thank you very much for your help.",
        "difficulty": Difficulty.easy,
        "category": "small-talk",
    },
    {
        "text": "Have you ever traveled outside your country?",
        "difficulty": Difficulty.medium,
        "category": "small-talk",
    },
    {
        "text": "Could you please repeat that a little slower?",
        "difficulty": Difficulty.medium,
        "category": "small-talk",
    },
    {
        "text": "I'm trying to improve my pronunciation every day.",
        "difficulty": Difficulty.medium,
        "category": "small-talk",
    },
    {
        "text": "Simultaneous interpretation requires extraordinary concentration and linguistic fluency.",
        "difficulty": Difficulty.hard,
        "category": "small-talk",
    },
    # --- food ---
    {
        "text": "I would like a cup of coffee, please.",
        "difficulty": Difficulty.easy,
        "category": "food",
    },
    {
        "text": "Can I have the menu, please?",
        "difficulty": Difficulty.easy,
        "category": "food",
    },
    {
        "text": "This soup tastes great.",
        "difficulty": Difficulty.easy,
        "category": "food",
    },
    {
        "text": "I would like to book a table for two.",
        "difficulty": Difficulty.medium,
        "category": "food",
    },
    {
        "text": "The restaurant was fully booked last night.",
        "difficulty": Difficulty.medium,
        "category": "food",
    },
    {
        "text": "They renovated the entire kitchen last summer.",
        "difficulty": Difficulty.medium,
        "category": "food",
    },
    {
        "text": "The sommelier recommended an exquisite Bordeaux with the caramelized shallots.",
        "difficulty": Difficulty.hard,
        "category": "food",
    },
    # --- travel ---
    {
        "text": "Where is the bus stop?",
        "difficulty": Difficulty.easy,
        "category": "travel",
    },
    {
        "text": "How much does this ticket cost?",
        "difficulty": Difficulty.easy,
        "category": "travel",
    },
    {
        "text": "I am going on vacation next week.",
        "difficulty": Difficulty.easy,
        "category": "travel",
    },
    {
        "text": "Could you tell me where the nearest station is?",
        "difficulty": Difficulty.medium,
        "category": "travel",
    },
    {
        "text": "Public transportation here is quite reliable.",
        "difficulty": Difficulty.medium,
        "category": "travel",
    },
    {
        "text": "The airport was extremely crowded this afternoon.",
        "difficulty": Difficulty.medium,
        "category": "travel",
    },
    {
        "text": "The architecture of the cathedral reflects centuries of cultural evolution.",
        "difficulty": Difficulty.hard,
        "category": "travel",
    },
    # --- weather ---
    {
        "text": "It is sunny outside today.",
        "difficulty": Difficulty.easy,
        "category": "weather",
    },
    {
        "text": "I think it might rain later.",
        "difficulty": Difficulty.easy,
        "category": "weather",
    },
    {
        "text": "The weather forecast says it will be cloudy tomorrow.",
        "difficulty": Difficulty.medium,
        "category": "weather",
    },
    {
        "text": "My favorite season is autumn because of the colors.",
        "difficulty": Difficulty.medium,
        "category": "weather",
    },
    {
        "text": "Meteorologists predict unusually turbulent atmospheric conditions this weekend.",
        "difficulty": Difficulty.hard,
        "category": "weather",
    },
    # --- tongue-twisters ---
    {
        "text": "Toy boat, toy boat, toy boat.",
        "difficulty": Difficulty.easy,
        "category": "tongue-twisters",
    },
    {
        "text": "Six slippery snails slid slowly seaward.",
        "difficulty": Difficulty.medium,
        "category": "tongue-twisters",
    },
    {
        "text": "She sells seashells by the seashore.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "Peter Piper picked a peck of pickled peppers.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "How much wood would a woodchuck chuck if a woodchuck could chuck wood?",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "Red lorry, yellow lorry.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "The sixth sick sheikh's sixth sheep's sick.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "I saw a kitten eating chicken in the kitchen.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "Irish wristwatch, Swiss wristwatch.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "Unique New York, unique New York, you know you need unique New York.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "Thirty-three thieves thought that they thrilled the throne throughout Thursday.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    {
        "text": "A proper copper coffee pot.",
        "difficulty": Difficulty.hard,
        "category": "tongue-twisters",
    },
    # ========================== professional / domain registers ==========================
    # --- business ---
    {
        "text": "I have a meeting at nine.",
        "difficulty": Difficulty.easy,
        "category": "business",
    },
    {
        "text": "Let's schedule a call tomorrow.",
        "difficulty": Difficulty.easy,
        "category": "business",
    },
    {
        "text": "She works as a software engineer downtown.",
        "difficulty": Difficulty.medium,
        "category": "business",
    },
    {
        "text": "We need to finish this project by Friday.",
        "difficulty": Difficulty.medium,
        "category": "business",
    },
    {
        "text": "It was a pleasure doing business with you.",
        "difficulty": Difficulty.medium,
        "category": "business",
    },
    {
        "text": "Unfortunately, the meeting has been rescheduled to next Thursday.",
        "difficulty": Difficulty.medium,
        "category": "business",
    },
    {
        "text": "The entrepreneur negotiated a particularly complicated merger agreement.",
        "difficulty": Difficulty.hard,
        "category": "business",
    },
    {
        "text": "The pharmaceutical company announced a groundbreaking clinical trial yesterday.",
        "difficulty": Difficulty.hard,
        "category": "business",
    },
    # --- customer-service ---
    {
        "text": "How can I help you?",
        "difficulty": Difficulty.easy,
        "category": "customer-service",
    },
    {
        "text": "I would like a refund, please.",
        "difficulty": Difficulty.easy,
        "category": "customer-service",
    },
    {
        "text": "I am sorry for the inconvenience; let me check your order.",
        "difficulty": Difficulty.medium,
        "category": "customer-service",
    },
    {
        "text": "Could you give me your reference number, please?",
        "difficulty": Difficulty.medium,
        "category": "customer-service",
    },
    {
        "text": "I will escalate your complaint to our specialist resolution department immediately.",
        "difficulty": Difficulty.hard,
        "category": "customer-service",
    },
    {
        "text": "Unfortunately the reimbursement cannot be authorized without the original documentation.",
        "difficulty": Difficulty.hard,
        "category": "customer-service",
    },
    # --- education ---
    {
        "text": "The lecture starts at ten.",
        "difficulty": Difficulty.easy,
        "category": "education",
    },
    {
        "text": "I forgot my homework again.",
        "difficulty": Difficulty.easy,
        "category": "education",
    },
    {
        "text": "Students must submit their assignments before the enrollment deadline.",
        "difficulty": Difficulty.medium,
        "category": "education",
    },
    {
        "text": "She is studying psychology at a university abroad.",
        "difficulty": Difficulty.medium,
        "category": "education",
    },
    {
        "text": "The curriculum emphasizes interdisciplinary methodology over rote memorization.",
        "difficulty": Difficulty.hard,
        "category": "education",
    },
    {
        "text": "Undergraduate enrollment fluctuated considerably throughout the academic year.",
        "difficulty": Difficulty.hard,
        "category": "education",
    },
    # --- engineering ---
    {
        "text": "The machine needs new parts.",
        "difficulty": Difficulty.easy,
        "category": "engineering",
    },
    {
        "text": "Check the pressure gauge first.",
        "difficulty": Difficulty.easy,
        "category": "engineering",
    },
    {
        "text": "The specification requires a tolerance of half a millimeter.",
        "difficulty": Difficulty.medium,
        "category": "engineering",
    },
    {
        "text": "Scheduled maintenance will begin at the end of the month.",
        "difficulty": Difficulty.medium,
        "category": "engineering",
    },
    {
        "text": "The structural engineer recalculated the load-bearing tolerances after the hydraulic failure.",
        "difficulty": Difficulty.hard,
        "category": "engineering",
    },
    {
        "text": "Manufacturing thermodynamically stable alloys requires extraordinarily precise temperature control.",
        "difficulty": Difficulty.hard,
        "category": "engineering",
    },
    # --- finance ---
    {
        "text": "Please send me the invoice.",
        "difficulty": Difficulty.easy,
        "category": "finance",
    },
    {
        "text": "The interest rate went up again.",
        "difficulty": Difficulty.easy,
        "category": "finance",
    },
    {
        "text": "Our quarterly revenue exceeded the analysts' expectations this year.",
        "difficulty": Difficulty.medium,
        "category": "finance",
    },
    {
        "text": "I would like to refinance my mortgage at a lower rate.",
        "difficulty": Difficulty.medium,
        "category": "finance",
    },
    {
        "text": "Depreciation and amortization significantly distorted the consolidated financial statements.",
        "difficulty": Difficulty.hard,
        "category": "finance",
    },
    {
        "text": "The fiduciary recommended diversifying the portfolio across several asset classes.",
        "difficulty": Difficulty.hard,
        "category": "finance",
    },
    # --- information-technology ---
    {
        "text": "Please turn off your phone.",
        "difficulty": Difficulty.easy,
        "category": "information-technology",
    },
    {
        "text": "My laptop battery is low.",
        "difficulty": Difficulty.easy,
        "category": "information-technology",
    },
    {
        "text": "Can you send me the file?",
        "difficulty": Difficulty.easy,
        "category": "information-technology",
    },
    {
        "text": "I forgot to charge my phone this morning.",
        "difficulty": Difficulty.medium,
        "category": "information-technology",
    },
    {
        "text": "The internet connection has been unstable lately.",
        "difficulty": Difficulty.medium,
        "category": "information-technology",
    },
    {
        "text": "This application keeps crashing unexpectedly.",
        "difficulty": Difficulty.medium,
        "category": "information-technology",
    },
    {
        "text": "We deploy the new release every second Tuesday.",
        "difficulty": Difficulty.medium,
        "category": "information-technology",
    },
    {
        "text": "Artificial intelligence is rapidly transforming numerous industries worldwide.",
        "difficulty": Difficulty.hard,
        "category": "information-technology",
    },
    {
        "text": "The deployment failed because the authentication service exceeded its latency threshold.",
        "difficulty": Difficulty.hard,
        "category": "information-technology",
    },
    {
        "text": "Our engineers migrated the entire repository to a containerized infrastructure.",
        "difficulty": Difficulty.hard,
        "category": "information-technology",
    },
    # --- job-interview ---
    {
        "text": "Tell me about your last job.",
        "difficulty": Difficulty.easy,
        "category": "job-interview",
    },
    {
        "text": "When can you start working?",
        "difficulty": Difficulty.easy,
        "category": "job-interview",
    },
    {
        "text": "I have five years of experience managing international teams.",
        "difficulty": Difficulty.medium,
        "category": "job-interview",
    },
    {
        "text": "What are your salary expectations for this position?",
        "difficulty": Difficulty.medium,
        "category": "job-interview",
    },
    {
        "text": "My greatest strength is prioritizing competing responsibilities under considerable pressure.",
        "difficulty": Difficulty.hard,
        "category": "job-interview",
    },
    {
        "text": "I thoroughly researched your organization's strategic objectives before applying.",
        "difficulty": Difficulty.hard,
        "category": "job-interview",
    },
    # --- legal ---
    {
        "text": "Please sign the contract here.",
        "difficulty": Difficulty.easy,
        "category": "legal",
    },
    {
        "text": "I need to call my lawyer.",
        "difficulty": Difficulty.easy,
        "category": "legal",
    },
    {
        "text": "The tenant is liable for any damage to the property.",
        "difficulty": Difficulty.medium,
        "category": "legal",
    },
    {
        "text": "Both parties agreed to settle the dispute out of court.",
        "difficulty": Difficulty.medium,
        "category": "legal",
    },
    {
        "text": "The indemnification clause explicitly excludes consequential and punitive damages.",
        "difficulty": Difficulty.hard,
        "category": "legal",
    },
    {
        "text": "Counsel argued that the tribunal lacked jurisdiction over the subsidiary.",
        "difficulty": Difficulty.hard,
        "category": "legal",
    },
    # --- medical ---
    {
        "text": "I have a sore throat today.",
        "difficulty": Difficulty.easy,
        "category": "medical",
    },
    {
        "text": "The doctor will see you now.",
        "difficulty": Difficulty.easy,
        "category": "medical",
    },
    {
        "text": "The patient was prescribed antibiotics for a chest infection.",
        "difficulty": Difficulty.medium,
        "category": "medical",
    },
    {
        "text": "Please describe your symptoms and any allergies you have.",
        "difficulty": Difficulty.medium,
        "category": "medical",
    },
    {
        "text": "The anesthesiologist monitored the patient's vital signs throughout the procedure.",
        "difficulty": Difficulty.hard,
        "category": "medical",
    },
    {
        "text": "She was diagnosed with pneumonia after a thorough radiological examination.",
        "difficulty": Difficulty.hard,
        "category": "medical",
    },
    # --- public-speaking ---
    {
        "text": "Thank you all for coming.",
        "difficulty": Difficulty.easy,
        "category": "public-speaking",
    },
    {
        "text": "Let's move to the next slide.",
        "difficulty": Difficulty.easy,
        "category": "public-speaking",
    },
    {
        "text": "In this presentation I will cover three main points.",
        "difficulty": Difficulty.medium,
        "category": "public-speaking",
    },
    {
        "text": "Are there any questions before we continue?",
        "difficulty": Difficulty.medium,
        "category": "public-speaking",
    },
    {
        "text": "To summarize, our findings suggest a fundamentally different strategic approach.",
        "difficulty": Difficulty.hard,
        "category": "public-speaking",
    },
    {
        "text": "I would like to acknowledge everyone whose collaboration made this achievement possible.",
        "difficulty": Difficulty.hard,
        "category": "public-speaking",
    },
    # --- science ---
    {
        "text": "We did an experiment today.",
        "difficulty": Difficulty.easy,
        "category": "science",
    },
    {
        "text": "The results look very clear.",
        "difficulty": Difficulty.easy,
        "category": "science",
    },
    {
        "text": "The researchers measured the temperature every fifteen minutes.",
        "difficulty": Difficulty.medium,
        "category": "science",
    },
    {
        "text": "Our hypothesis was not supported by the experimental data.",
        "difficulty": Difficulty.medium,
        "category": "science",
    },
    {
        "text": "Several competing hypotheses were evaluated using statistically rigorous methodology.",
        "difficulty": Difficulty.hard,
        "category": "science",
    },
    {
        "text": "Photosynthesis converts electromagnetic radiation into chemical energy remarkably efficiently.",
        "difficulty": Difficulty.hard,
        "category": "science",
    },
    # ============================== phonetics drill sets ==============================
    # --- idioms ---
    {
        "text": "It costs an arm and a leg.",
        "difficulty": Difficulty.easy,
        "category": "idioms",
    },
    {
        "text": "Break a leg tomorrow.",
        "difficulty": Difficulty.easy,
        "category": "idioms",
    },
    {
        "text": "Let's play it by ear and decide in the morning.",
        "difficulty": Difficulty.medium,
        "category": "idioms",
    },
    {
        "text": "She let the cat out of the bag before the announcement.",
        "difficulty": Difficulty.medium,
        "category": "idioms",
    },
    {
        "text": "Speaking off the cuff, I would say we are barking up the wrong tree.",
        "difficulty": Difficulty.hard,
        "category": "idioms",
    },
    {
        "text": "He was caught between a rock and a hard place throughout the negotiation.",
        "difficulty": Difficulty.hard,
        "category": "idioms",
    },
    # --- minimal-pairs ---
    {
        "text": "The ship is bigger than a sheep.",
        "difficulty": Difficulty.easy,
        "category": "minimal-pairs",
    },
    {
        "text": "I think the sink is leaking.",
        "difficulty": Difficulty.easy,
        "category": "minimal-pairs",
    },
    {
        "text": "The bat looked bad today.",
        "difficulty": Difficulty.easy,
        "category": "minimal-pairs",
    },
    {
        "text": "She said the rice arrived but I heard lice instead.",
        "difficulty": Difficulty.medium,
        "category": "minimal-pairs",
    },
    {
        "text": "Only a fool would leave the full bucket outside.",
        "difficulty": Difficulty.medium,
        "category": "minimal-pairs",
    },
    {
        "text": "Saying thin instead of tin can completely change your meaning.",
        "difficulty": Difficulty.hard,
        "category": "minimal-pairs",
    },
    {
        "text": "Confusing berry with very is a very common pronunciation mistake.",
        "difficulty": Difficulty.hard,
        "category": "minimal-pairs",
    },
    # --- numbers-and-dates ---
    {
        "text": "The meeting is on May thirteenth.",
        "difficulty": Difficulty.easy,
        "category": "numbers-and-dates",
    },
    {
        "text": "It costs thirty dollars and fifteen cents.",
        "difficulty": Difficulty.easy,
        "category": "numbers-and-dates",
    },
    {
        "text": "Please call me back at four fifteen on Wednesday afternoon.",
        "difficulty": Difficulty.medium,
        "category": "numbers-and-dates",
    },
    {
        "text": "The contract expires on the thirtieth of September.",
        "difficulty": Difficulty.medium,
        "category": "numbers-and-dates",
    },
    {
        "text": "Between nineteen thirteen and nineteen thirty the population tripled.",
        "difficulty": Difficulty.hard,
        "category": "numbers-and-dates",
    },
    {
        "text": "The fortieth anniversary falls on the twenty-fifth of February.",
        "difficulty": Difficulty.hard,
        "category": "numbers-and-dates",
    },
]


def seed_phrases(session: Session) -> None:
    existing = {p.text: p for p in session.exec(select(Phrase)).all()}
    new_rows = [Phrase(**p) for p in PHRASES if p["text"] not in existing]
    session.add_all(new_rows)

    # Seeding is keyed on `text`, so an edit to an already-seeded phrase's
    # category or difficulty (e.g. the technology -> information-technology
    # rename) would otherwise never reach an existing database.
    for spec in PHRASES:
        row = existing.get(spec["text"])
        if row is None:
            continue
        if (row.category, row.difficulty) != (spec["category"], spec["difficulty"]):
            row.category = spec["category"]
            row.difficulty = spec["difficulty"]
            session.add(row)

    session.commit()
