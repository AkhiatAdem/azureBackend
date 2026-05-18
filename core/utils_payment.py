def simulate_payment(card_number):
    """
    Demo transaction logic for the PFE jury presentation.

    The React form handles the friendly expiry-date check, while the backend
    simply approves any non-empty card number containing exactly 16 digits.
    """
    if not card_number:
        return False
    
    # Remove spaces/dashes
    clean_number = "".join(c for c in card_number if c.isdigit())
    
    if len(clean_number) == 16:
        return True
    return False
