from app.categorizer import INCOME, OTHER, categorize, merchant_key
from app.models import TxType

D = TxType.DEBIT


def test_keywords():
    assert categorize("UPI/DR/ZOMATO LTD", D) == "Food & Dining"
    assert categorize("Rapido bike ride", D) == "Travel & Transport"
    assert categorize("Airtel prepaid recharge", D) == "Bills & Utilities"
    assert categorize("Netflix monthly", D) == "Subscriptions & Entertainment"
    assert categorize("Blinkit order", D) == "Groceries"


def test_whole_word_matching_avoids_old_false_positives():
    # old JS: "vi" matched service, "tea" matched steam-> wrong; "fee" matched coffee
    assert categorize("Laundry service", D) == OTHER
    assert categorize("Coffee day", D) == "Food & Dining"
    assert categorize("Steam games", D) == "Subscriptions & Entertainment"


def test_credit_is_income():
    assert categorize("Zomato refund", TxType.CREDIT) == INCOME


def test_learned_rules_win():
    learned = {merchant_key("UPI/DR/123/RAMESH STORES/ramesh@ybl"): "Groceries"}
    assert categorize("UPI/DR/999/RAMESH STORES/ramesh@ybl", D, learned) == "Groceries"


def test_hint_used_when_valid():
    assert categorize("xyz", D, hint="health") == "Health"
    assert categorize("xyz", D, hint="nonsense") == OTHER
