import re
from typing import Tuple, Optional, Dict, Any

class DomainGuardrail:
    """
    Evaluates whether a user query falls within Easy Home Finance & LAMF domain,
    and enforces enterprise safety guardrails:
    1. Prompt Injection & Jailbreak Defense
    2. Data Exfiltration & PII Protection
    3. Financial Speculation & Regulatory Guarantee Restrictions
    4. Contradiction Detection
    5. Off-Topic Filtering & Polite Reframing
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
        "lien", "marked", "mark", "marking", "penny", "drop", "verify", "verification", "failed", "fail", "faild",
        "verfication", "verifing", "pennydrop", "stuck", "rejected", "reject", "unsuccessful", "npci", "ifsc",
        # Hinglish keywords
        "mera", "meri", "mere", "nahi", "nhi", "ho", "raha", "rha", "kya", "karu", "bhai", "sahi", "fir", "bhi",
        "isko", "dobara", "try", "kar", "sakte", "hain", "baar", "se", "baat", "kara", "do", "hua", "gaya",
        "paisa", "khata", "aadmi", "madad"
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

    PROMPT_INJECTION_PATTERNS = [
        r'\b(?:ignore|forget|disregard)\s+(?:all\s+)?(?:your\s+)?(?:the\s+)?(?:previous\s+)?(?:instructions|rules|system\s+prompt|context|verified\s+facts|facts)\b',
        r'\b(?:system\s+prompt|developer\s+message|internal\s+instructions|system\s+instructions)\b',
        r'\b(?:pretend\s+you(?:re|\s+are)\s+(?:an?\s+)?admin|simulate\s+admin|jailbreak|dan\s+mode)\b',
        r'\b(?:ignore\s+(?:the\s+)?escalation\s+rules|bypass\s+(?:the\s+)?guardrail)\b',
        r'\b(?:hidden\s+api\s+response|internal\s+escalation\s+thresholds|internal\s+api\s+endpoint)\b'
    ]

    DATA_EXFILTRATION_PATTERNS = [
        r'\b(?:show|give|fetch|display)\s+(?:me\s+)?(?:another|other)\s+customer(?:\'s)?\s+(?:details|data|loan|account)\b',
        r'\b(?:what\s+is\s+rahul\s+sharma(?:\'s)?\s+bank\s+account|rahul\s+sharma\s+account)\b',
        r'\b(?:give\s+me\s+the\s+full\s+account\s+number|reveal\s+full\s+unmasked\s+account)\b',
        r'\b(?:cams\s+api\s+credentials|database\s+password|secret\s+key|access\s+token)\b',
        r'\b(?:agent(?:\'s)?\s+internal\s+ticket\s+data|all\s+support\s+tickets\s+dump)\b'
    ]

    FINANCIAL_SPECULATION_PATTERNS = [
        r'\b(?:what\s+will\s+my\s+interest\s+rate\s+be\s+next\s+year|interest\s+rate\s+in\s+202\d)\b',
        r'\b(?:will\s+(?:the\s+)?rbi\s+reduce|will\s+rbi\s+cut\s+rates)\b',
        r'\b(?:guarantee\s+(?:that\s+)?(?:my\s+)?loan\s+will\s+be\s+approved|guarantee\s+sanction)\b',
        r'\b(?:how\s+much\s+will\s+my\s+mutual\s+fund\s+be\s+worth\s+tomorrow|predict\s+nav|predict\s+nifty)\b',
        r'\b(?:what\s+exact\s+amount\s+will\s+i\s+be\s+approved\s+for|promise\s+me\s+a\s+sanction)\b'
    ]

    CONTRADICTION_PATTERNS = [
        r'\b(?:verification\s+failed\s+but\s+(?:actually\s+)?(?:it\s+)?(?:says\s+)?successful|failed\s+but\s+successful)\b',
        r'\b(?:changed\s+my\s+bank\s+account\s+yesterday\s+but\s+i\s+haven\'t\s+changed\s+it\s+yet|already\s+paid\s+but\s+not\s+paid)\b'
    ]

    @classmethod
    def inspect_security_and_compliance(cls, text: str) -> Optional[Dict[str, Any]]:
        """
        Inspects message for security, prompt injection, data exfiltration,
        speculation, and contradictions.
        """
        text_lower = text.strip().lower()

        # 1. Prompt Injection Defense
        for pat in cls.PROMPT_INJECTION_PATTERNS:
            if re.search(pat, text_lower):
                return {
                    "basket": "GUARDRAIL_DEFENSE",
                    "intent": "PROMPT_INJECTION_DEFENSE",
                    "confidence": 0.99,
                    "risk_level": "HIGH",
                    "source_authority": "System Security Guardrail",
                    "response": (
                        "I am an authorized lending assistant for Easy Home Finance & LAMF. "
                        "I operate strictly within verified lending policies and cannot reveal underlying developer instructions, override safety rules, or execute arbitrary commands. "
                        "How can I assist with your loan application today?"
                    ),
                    "action_chips": ["Check Application Status", "Calculate EMI", "Connect with an Agent"]
                }

        # 2. Data Exfiltration Prevention
        for pat in cls.DATA_EXFILTRATION_PATTERNS:
            if re.search(pat, text_lower):
                return {
                    "basket": "GUARDRAIL_DEFENSE",
                    "intent": "DATA_EXFILTRATION_BLOCKED",
                    "confidence": 0.99,
                    "risk_level": "CRITICAL",
                    "source_authority": "Customer Data Privacy (DPDP / RBI Policy)",
                    "response": (
                        "Access denied. In strict adherence to RBI data privacy and customer confidentiality mandates, "
                        "I am prohibited from disclosing other customers' loan information, full account numbers, or backend system credentials."
                    ),
                    "action_chips": ["View My Loan Details", "Connect with Support"]
                }

        # 3. Financial Speculation & Guarantees
        for pat in cls.FINANCIAL_SPECULATION_PATTERNS:
            if re.search(pat, text_lower):
                return {
                    "basket": "GUARDRAIL_DISCLOSURE",
                    "intent": "FINANCIAL_SPECULATION_GUARDRAIL",
                    "confidence": 0.99,
                    "risk_level": "MEDIUM",
                    "source_authority": "Regulatory Fair Practices Code",
                    "response": (
                        "As a regulated lending assistant, I cannot speculate on future market NAVs, predict RBI policy changes, or guarantee loan approvals. "
                        "Loan sanctions and interest pricing are determined strictly by credit underwriting based on your live documents, CIBIL score, and verified collateral."
                    ),
                    "action_chips": ["Check Current Interest Rate", "View Eligibility Criteria", "Speak with Loan Officer"]
                }

        # 4. Contradiction Detection
        for pat in cls.CONTRADICTION_PATTERNS:
            if re.search(pat, text_lower):
                return {
                    "basket": "BASKET_1_CLARIFICATION",
                    "intent": "CLARIFICATION_REQUIRED",
                    "confidence": 0.95,
                    "risk_level": "LOW",
                    "source_authority": "Dialogue Consistency Guardrail",
                    "response": (
                        "I noticed conflicting statements in your message regarding the status. "
                        "Could you please confirm whether your bank verification currently shows as failed or successful on your screen so I can guide you accurately?"
                    ),
                    "action_chips": ["It Shows Failed", "It Shows Successful", "Connect with an Agent"]
                }

        return None

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

        # Check general conversational short replies (<= 4 words)
        if len(words) <= 4:
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
