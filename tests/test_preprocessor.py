from src.classifier.preprocessor import MAX_MESSAGE_LENGTH, preprocess


def test_empty_message_detected() -> None:
    result = preprocess("   ")
    assert result.is_empty is True


def test_long_message_truncated() -> None:
    result = preprocess("a" * (MAX_MESSAGE_LENGTH + 10))
    assert result.was_truncated is True
    assert len(result.text) == MAX_MESSAGE_LENGTH


def test_normalization_removes_accents_for_search() -> None:
    result = preprocess("¡Me quiero hacer daño!")
    assert "dano" in result.searchable_text


def test_language_hint_is_used() -> None:
    result = preprocess("Appointment please", language_hint="en")
    assert result.detected_language == "en"
