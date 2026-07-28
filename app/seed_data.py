from sqlmodel import Session, select

from app.models import Difficulty, Phrase

PHRASES: list[dict] = [
    # --- easy ---
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
        "text": "What time is it now?",
        "difficulty": Difficulty.easy,
        "category": "small-talk",
    },
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
        "text": "Please turn off your phone.",
        "difficulty": Difficulty.easy,
        "category": "technology",
    },
    {
        "text": "My laptop battery is low.",
        "difficulty": Difficulty.easy,
        "category": "technology",
    },
    {
        "text": "Can you send me the file?",
        "difficulty": Difficulty.easy,
        "category": "technology",
    },
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
        "text": "Thank you very much for your help.",
        "difficulty": Difficulty.easy,
        "category": "small-talk",
    },
    # --- medium ---
    {
        "text": "Could you tell me where the nearest station is?",
        "difficulty": Difficulty.medium,
        "category": "travel",
    },
    {
        "text": "I would like to book a table for two.",
        "difficulty": Difficulty.medium,
        "category": "food",
    },
    {
        "text": "The weather forecast says it will be cloudy tomorrow.",
        "difficulty": Difficulty.medium,
        "category": "weather",
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
        "text": "Have you ever traveled outside your country?",
        "difficulty": Difficulty.medium,
        "category": "small-talk",
    },
    {
        "text": "The restaurant was fully booked last night.",
        "difficulty": Difficulty.medium,
        "category": "food",
    },
    {
        "text": "I forgot to charge my phone this morning.",
        "difficulty": Difficulty.medium,
        "category": "technology",
    },
    {
        "text": "Public transportation here is quite reliable.",
        "difficulty": Difficulty.medium,
        "category": "travel",
    },
    {
        "text": "The internet connection has been unstable lately.",
        "difficulty": Difficulty.medium,
        "category": "technology",
    },
    {
        "text": "My favorite season is autumn because of the colors.",
        "difficulty": Difficulty.medium,
        "category": "weather",
    },
    {
        "text": "It was a pleasure doing business with you.",
        "difficulty": Difficulty.medium,
        "category": "business",
    },
    {
        "text": "Could you please repeat that a little slower?",
        "difficulty": Difficulty.medium,
        "category": "small-talk",
    },
    {
        "text": "The airport was extremely crowded this afternoon.",
        "difficulty": Difficulty.medium,
        "category": "travel",
    },
    {
        "text": "I'm trying to improve my pronunciation every day.",
        "difficulty": Difficulty.medium,
        "category": "small-talk",
    },
    {
        "text": "This application keeps crashing unexpectedly.",
        "difficulty": Difficulty.medium,
        "category": "technology",
    },
    {
        "text": "They renovated the entire kitchen last summer.",
        "difficulty": Difficulty.medium,
        "category": "food",
    },
    {
        "text": "Unfortunately, the meeting has been rescheduled to next Thursday.",
        "difficulty": Difficulty.medium,
        "category": "business",
    },
    # --- hard ---
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
    {
        "text": "The entrepreneur negotiated a particularly complicated merger agreement.",
        "difficulty": Difficulty.hard,
        "category": "business",
    },
    {
        "text": "Meteorologists predict unusually turbulent atmospheric conditions this weekend.",
        "difficulty": Difficulty.hard,
        "category": "weather",
    },
    {
        "text": "The architecture of the cathedral reflects centuries of cultural evolution.",
        "difficulty": Difficulty.hard,
        "category": "travel",
    },
    {
        "text": "Artificial intelligence is rapidly transforming numerous industries worldwide.",
        "difficulty": Difficulty.hard,
        "category": "technology",
    },
    {
        "text": "The pharmaceutical company announced a groundbreaking clinical trial yesterday.",
        "difficulty": Difficulty.hard,
        "category": "business",
    },
    {
        "text": "Simultaneous interpretation requires extraordinary concentration and linguistic fluency.",
        "difficulty": Difficulty.hard,
        "category": "small-talk",
    },
]


def seed_phrases(session: Session) -> None:
    existing = set(session.exec(select(Phrase.text)).all())
    new_rows = [Phrase(**p) for p in PHRASES if p["text"] not in existing]
    if new_rows:
        session.add_all(new_rows)
        session.commit()
