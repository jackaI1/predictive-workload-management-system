"""Tests for the task-name parsing helpers.

These functions turn free-text task titles typed by humans into structured target
sets, so they carry most of the pipeline's ambiguity. Every fixture below is an
invented title in the shape the parsers expect -- none is taken from real work.
"""

from expander import (
    extract_allowed_targets,
    is_wildcard_numeric_match,
    parse_compound_suffixes,
    parse_number_sequence,
)


# --------------------------------------------------------------------------
# parse_number_sequence
# --------------------------------------------------------------------------

def test_expands_a_to_range():
    assert parse_number_sequence("1 TO 5") == [1, 2, 3, 4, 5]


def test_expands_a_hyphen_range():
    assert parse_number_sequence("12-18") == [12, 13, 14, 15, 16, 17, 18]


def test_tolerates_a_comma_before_to():
    """Titles are typed by hand; '1, to 4' is as common as '1 to 4'."""
    assert parse_number_sequence("1, TO 4") == [1, 2, 3, 4]


def test_handles_multiple_ranges_in_one_segment():
    assert parse_number_sequence("1, TO 4, 6 TO 8") == [1, 2, 3, 4, 6, 7, 8]


def test_mixes_ranges_and_loose_numbers():
    assert parse_number_sequence("2 TO 4, 9") == [2, 3, 4, 9]


def test_single_number_returns_itself():
    assert parse_number_sequence("7") == [7]


def test_empty_segment_returns_empty_list():
    assert parse_number_sequence("") == []


def test_result_is_sorted_and_deduplicated():
    assert parse_number_sequence("5, 1 TO 3, 2") == [1, 2, 3, 5]


def test_is_case_insensitive():
    assert parse_number_sequence("1 to 3") == parse_number_sequence("1 TO 3")


# --------------------------------------------------------------------------
# parse_compound_suffixes
# --------------------------------------------------------------------------

def test_expands_a_numeric_suffix_range():
    assert parse_compound_suffixes("1 TO 3") == ["1", "2", "3"]


def test_splits_a_comma_separated_list():
    assert parse_compound_suffixes("A, B") == ["A", "B"]


def test_combines_a_range_with_loose_items():
    got = parse_compound_suffixes("1-3, X")
    assert got == ["1", "2", "3", "X"]


def test_uppercases_its_input():
    assert parse_compound_suffixes("a, b") == ["A", "B"]


def test_ignores_empty_segments():
    assert parse_compound_suffixes("A, , B") == ["A", "B"]


def test_empty_input_yields_no_suffixes():
    assert parse_compound_suffixes("") == []


# --------------------------------------------------------------------------
# is_wildcard_numeric_match
# --------------------------------------------------------------------------

def test_plural_numeric_model_matches_a_containing_cell():
    assert is_wildcard_numeric_match("100S", "1001")


def test_plural_numeric_model_matches_a_trailing_zero_stripped_prefix():
    assert is_wildcard_numeric_match("100S", "1")


def test_non_plural_model_never_wildcard_matches():
    assert not is_wildcard_numeric_match("100", "1001")


def test_plural_alphabetic_model_is_not_a_numeric_wildcard():
    assert not is_wildcard_numeric_match("ABCS", "ABC1")


def test_unrelated_cell_does_not_match():
    assert not is_wildcard_numeric_match("100S", "999")


# --------------------------------------------------------------------------
# extract_allowed_targets
# --------------------------------------------------------------------------

def test_returns_nothing_without_a_project_code():
    project, models, blocks, lots = extract_allowed_targets("no code in this title")
    assert project is None
    assert models == set() and blocks == set() and lots == set()


def test_extracts_the_project_code():
    project, _, _, _ = extract_allowed_targets("D12345 BLOCK 1")
    assert project == "D12345"


def test_accepts_a_six_digit_project_code():
    project, _, _, _ = extract_allowed_targets("D123456 BLOCK 1")
    assert project == "D123456"


def test_expands_a_block_range():
    _, _, blocks, _ = extract_allowed_targets("D12345 BLOCK 1 TO 3")
    assert blocks == {"BLOCK 1", "BLOCK 2", "BLOCK 3"}


def test_accepts_the_blk_abbreviation():
    _, _, blocks, _ = extract_allowed_targets("D12345 BLK 2")
    assert "BLOCK 2" in blocks


def test_extracts_lots_separately_from_blocks():
    _, _, blocks, lots = extract_allowed_targets("D12345 LOT 5, 7")
    assert lots == {5, 7}
    assert blocks == set()


def test_review_suffix_is_trimmed_before_parsing():
    """'2ND REVIEW' is workflow metadata, not a target specification."""
    _, _, blocks_plain, _ = extract_allowed_targets("D12345 BLOCK 2")
    _, _, blocks_review, _ = extract_allowed_targets("D12345 BLOCK 2 2ND REVIEW")
    assert blocks_review == blocks_plain


def test_block_numbers_are_not_also_read_as_lots():
    _, _, blocks, lots = extract_allowed_targets("D12345 BLOCK 4")
    assert "BLOCK 4" in blocks
    assert 4 not in lots


# --------------------------------------------------------------------------
# The connecting word "AND"
#
# The original character class stopped at the letter 'A', so everything after
# an "AND" was silently discarded. These lock the fix in place.
# --------------------------------------------------------------------------

def test_and_is_recognised_between_lots():
    _, _, _, lots = extract_allowed_targets("D12345 LOT 5, 7 AND 9")
    assert lots == {5, 7, 9}


def test_and_is_recognised_between_blocks():
    _, _, blocks, _ = extract_allowed_targets("D12345 BLOCK 1 AND 3")
    assert blocks == {"BLOCK 1", "BLOCK 3"}


def test_ampersand_is_recognised():
    _, _, _, lots = extract_allowed_targets("D12345 LOT 5 & 7")
    assert lots == {5, 7}


def test_and_joining_a_block_to_a_lot_keeps_them_separate():
    _, _, blocks, lots = extract_allowed_targets("D12345 BLOCK 2 AND LOT 5")
    assert blocks == {"BLOCK 2"}
    assert lots == {5}


def test_and_combines_with_ranges():
    _, _, _, lots = extract_allowed_targets("D12345 LOT 1 TO 3 AND 9")
    assert lots == {1, 2, 3, 9}


def test_plural_lots_keyword_is_matched():
    _, _, _, lots = extract_allowed_targets("D12345 LOTS 5")
    assert lots == {5}
