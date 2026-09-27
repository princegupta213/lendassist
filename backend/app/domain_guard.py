import re
from typing import Tuple, Optional

class DomainGuardrail:
    """
    Evaluates whether a user query falls within Easy Home Finance & LAMF domain.
    Preserves all dialogic signals (e.g. 'one step at a time', 'unlock', numbers).
    """

    FINANCE_KEYWORDS = {
        "loan", "emi", "interest", "rate", "lamf", "mutual", "fund", "cams", "kfintech",
        "pledge", "unpledge", "kyc", "pan", "aadhaar", "document", "documents", "status",
        "track", "application", "sanction", "disbursement", "disburse", "property",
        "home", "housing", "mortgage", "salaried", "self-employed", "itr", "salary",
        "slip", "bank", "statement", "autopay", "mandate", "cibil", "credit", "score",
        "limit", "portfolio", "margin", "call", "nifty", "nav", "bounce", "foreclose",
        "prepay", "ltv", "elss", "tax", "capital", "gains", "stcg", "ltcg", "apr",
        "fee", "charge", "charges", "agent", "human", "support", "help", "apply", "hi", "hello", "hey",
        "step", "steps", "unlock", "max", "full", "start", "next", "ok", "okay", "proceed", "yes", "sure", "let", "do", "it", "sign",
        "agreement", "kfs", "point", "points", "terms", "contract", "explain", "key", "die", "death", "nominee",
        "transmission", "deceased", "settlement", "account", "balance", "withdrawable", "draw", "drawdown",
        "lien", "marked", "mark", "marking"
    }

    OFF_TOPIC_PATTERNS = [
        r'\b(?:poem|poetry|song|lyrics|rhyme)\b',
        r'\b(?:recipe|cook|bake|ingredients|cake|pizza|food|burger)\b',
        r'\b(?:cricket|football|world cup|ipl|match|messi|ronaldo)\b',
        r'\b(?:crypto|bitcoin|ethereum|doge|binance|nft|dogecoin)\b',
        r'\b(?:joke|riddle|funny|meme)\b',
        r'\b(?:weather|temperature|forecast|rain today)\b',
        r'\b(?:who is the president|prime minister|capital of france)\b'
    ]

    @classmethod
    def check_query_domain(cls, text: str) -> Tuple[bool, Optional[str]]:
        text_lower = text.strip().lower()
        words = set(re.findall(r'\b\w+\b', text_lower))

        # Check explicit off-topic patterns
        for pattern in cls.OFF_TOPIC_PATTERNS:
            if re.search(pattern, text_lower):
                return False, cls._generate_off_topic_reply(text_lower)

        # Allow conversational phrases or numbers
        if any(c.isdigit() for c in text_lower):
            return True, None

        if any(w in words for w in cls.FINANCE_KEYWORDS):
            return True, None

        # Check general conversational short replies (<= 3 words)
        if len(words) <= 3:
            return True, None

        return False, cls._generate_off_topic_reply(text_lower)

    @classmethod
    def _generate_off_topic_reply(cls, query: str) -> str:
        if any(w in query for w in ["crypto", "bitcoin", "ethereum", "dogecoin"]):
            return (
                "We do not offer loans against cryptocurrency. We provide loans exclusively against SEBI-regulated mutual funds and homes. "
                "Would you like to check your mutual fund loan limit?"
            )
        return "I focus strictly on Home Loans and credit lines against mutual funds. Would you like to explore your loan options?"
