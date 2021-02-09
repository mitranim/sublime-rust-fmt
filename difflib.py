"""
Functions for diff, match and patch.

Computes the difference between two texts to create a patch.
Applies the patch onto another text, allowing for errors.

Originally found at http://code.google.com/p/google-diff-match-patch/.
Edited for clarity and simplicity by Nelo Mitranim, 2017.
"""

import re
from collections import namedtuple

class Ops(object):
    EQUAL  = 'EQUAL'
    INSERT = 'INSERT'
    DELETE = 'DELETE'

Diff = namedtuple('Diff', ['op', 'text'])

# Cost of an empty edit operation in terms of edit characters.
DIFF_EDIT_COST = 4

BLANK_LINE_END = re.compile(r"\n\r?\n$")

BLANK_LINE_START = re.compile(r"^\r?\n\r?\n")

def myers_diffs(text1, text2, checklines=True):
    """Find the differences between two texts.  Simplifies the problem by
        stripping any common prefix or suffix off the texts before diffing.

    Args:
        text1: Old string to be diffed.
        text2: New string to be diffed.
        checklines: Optional speedup flag.  If present and false, then don't run
            a line-level diff first to identify the changed areas.
            Defaults to true, which does a faster, slightly less optimal diff.

    Returns:
        List of changes.
    """
    if text1 == None or text2 == None:
        raise ValueError('Null inputs (myers_diffs)')

    # Check for equality (speedup).
    if text1 == text2:
        if text1:
            return [Diff(Ops.EQUAL, text1)]
        return []

    # Trim off common prefix (speedup).
    common_length = common_prefix_length(text1, text2)
    common_prefix = text1[:common_length]
    text1 = text1[common_length:]
    text2 = text2[common_length:]

    # Trim off common suffix (speedup).
    common_length = common_suffix_length(text1, text2)
    if common_length == 0:
        commonsuffix = ''
    else:
        commonsuffix = text1[-common_length:]
        text1 = text1[:-common_length]
        text2 = text2[:-common_length]

    # Compute the diff on the middle block.
    diffs = compute_diffs(text1, text2, checklines)

    # Restore the prefix and suffix.
    if common_prefix:
        diffs[:0] = [Diff(Ops.EQUAL, common_prefix)]
    if commonsuffix:
        diffs.append(Diff(Ops.EQUAL, commonsuffix))
    cleanup_merge(diffs)
    return diffs

def compute_diffs(text1, text2, checklines):
    """Find the differences between two texts.  Assumes that the texts do not
        have any common prefix or suffix.

    Args:
        text1: Old string to be diffed.
        text2: New string to be diffed.
        checklines: Speedup flag.  If false, then don't run a line-level diff
            first to identify the changed areas.
            If true, then run a faster, slightly less optimal diff.

    Returns:
        List of changes.
    """
    if not text1:
        # Just add some text (speedup).
        return [Diff(Ops.INSERT, text2)]

    if not text2:
        # Just delete some text (speedup).
        return [Diff(Ops.DELETE, text1)]

    if len(text1) > len(text2):
        (longtext, shorttext) = (text1, text2)
    else:
        (shorttext, longtext) = (text1, text2)
    i = longtext.find(shorttext)
    if i != -1:
        # Shorter text is inside the longer text (speedup).
        diffs = [Diff(Ops.INSERT, longtext[:i]), Diff(Ops.EQUAL, shorttext),
                         Diff(Ops.INSERT, longtext[i + len(shorttext):])]
        # Swap insertions for deletions if diff is reversed.
        if len(text1) > len(text2):
            diffs[0] = diffs[0]._replace(op=Ops.DELETE)
            diffs[2] = diffs[2]._replace(op=Ops.DELETE)
        return diffs

    if len(shorttext) == 1:
        # Single character string.
        # After the previous speedup, the character can't be an equality.
        return [Diff(Ops.DELETE, text1), Diff(Ops.INSERT, text2)]

    if checklines and len(text1) > 100 and len(text2) > 100:
        return line_mode_diffs(text1, text2)

    return diff_bisect(text1, text2)

def line_mode_diffs(text1, text2):
    """Do a quick line-level diff on both strings, then rediff the parts for
        greater accuracy.
        This speedup can produce non-minimal diffs.

    Args:
        text1: Old string to be diffed.
        text2: New string to be diffed.

    Returns:
        List of changes.
    """

    # Scan the text on a line-by-line basis first.
    (text1, text2, line_list) = lines_to_chars(text1, text2)

    diffs = myers_diffs(text1, text2, False)

    # Convert the diff back to original text.
    diffs = [diff._replace(text=''.join(line_list[ord(char)] for char in diff.text)) for diff in diffs]

    # Eliminate freak matches (e.g. blank lines)
    cleanup_semantic(diffs)

    # Rediff any replacement blocks, this time character-by-character.
    # Add a dummy entry at the end.
    diffs.append(Diff(Ops.EQUAL, ''))
    pointer = 0
    count_delete = 0
    count_insert = 0
    text_delete = ''
    text_insert = ''
    while pointer < len(diffs):
        if diffs[pointer].op == Ops.INSERT:
            count_insert += 1
            text_insert += diffs[pointer].text
        elif diffs[pointer].op == Ops.DELETE:
            count_delete += 1
            text_delete += diffs[pointer].text
        elif diffs[pointer].op == Ops.EQUAL:
            # Upon reaching an equality, check for prior redundancies.
            if count_delete >= 1 and count_insert >= 1:
                # Delete the offending records and add the merged ones.
                a = myers_diffs(text_delete, text_insert, False)
                diffs[pointer - count_delete - count_insert : pointer] = a
                pointer = pointer - count_delete - count_insert + len(a)
            count_insert = 0
            count_delete = 0
            text_delete = ''
            text_insert = ''

        pointer += 1

    diffs.pop()  # Remove the dummy entry at the end.

    return diffs

def diff_bisect(text1, text2):
    """Find the 'middle snake' of a diff, split the problem in two
        and return the recursively constructed diff.
        See Myers 1986 paper: An O(ND) Difference Algorithm and Its Variations.

    Args:
        text1: Old string to be diffed.
        text2: New string to be diffed.

    Returns:
        List of diff tuples.
    """

    # Cache the text lengths to prevent multiple calls.
    text1_length = len(text1)
    text2_length = len(text2)
    max_d = (text1_length + text2_length + 1) // 2
    v_offset = max_d
    v_length = 2 * max_d
    v1 = [-1] * v_length
    v1[v_offset + 1] = 0
    v2 = v1[:]
    delta = text1_length - text2_length
    # If the total number of characters is odd, then the front path will
    # collide with the reverse path.
    front = (delta % 2 != 0)
    # Offsets for start and end of k loop.
    # Prevents mapping of space beyond the grid.
    k1start = 0
    k1end = 0
    k2start = 0
    k2end = 0
    for d in range(max_d):
        # Walk the front path one step.
        for k1 in range(-d + k1start, d + 1 - k1end, 2):
            k1_offset = v_offset + k1
            if k1 == -d or (k1 != d and
                    v1[k1_offset - 1] < v1[k1_offset + 1]):
                x1 = v1[k1_offset + 1]
            else:
                x1 = v1[k1_offset - 1] + 1
            y1 = x1 - k1
            while (x1 < text1_length and y1 < text2_length and
                         text1[x1] == text2[y1]):
                x1 += 1
                y1 += 1
            v1[k1_offset] = x1
            if x1 > text1_length:
                # Ran off the right of the graph.
                k1end += 2
            elif y1 > text2_length:
                # Ran off the bottom of the graph.
                k1start += 2
            elif front:
                k2_offset = v_offset + delta - k1
                if k2_offset >= 0 and k2_offset < v_length and v2[k2_offset] != -1:
                    # Mirror x2 onto top-left coordinate system.
                    x2 = text1_length - v2[k2_offset]
                    if x1 >= x2:
                        # Overlap detected.
                        return bisect_split_diffs(text1, text2, x1, y1)

        # Walk the reverse path one step.
        for k2 in range(-d + k2start, d + 1 - k2end, 2):
            k2_offset = v_offset + k2
            if k2 == -d or (k2 != d and
                    v2[k2_offset - 1] < v2[k2_offset + 1]):
                x2 = v2[k2_offset + 1]
            else:
                x2 = v2[k2_offset - 1] + 1
            y2 = x2 - k2
            while (x2 < text1_length and y2 < text2_length and
                         text1[-x2 - 1] == text2[-y2 - 1]):
                x2 += 1
                y2 += 1
            v2[k2_offset] = x2
            if x2 > text1_length:
                # Ran off the left of the graph.
                k2end += 2
            elif y2 > text2_length:
                # Ran off the top of the graph.
                k2start += 2
            elif not front:
                k1_offset = v_offset + delta - k2
                if k1_offset >= 0 and k1_offset < v_length and v1[k1_offset] != -1:
                    x1 = v1[k1_offset]
                    y1 = v_offset + x1 - k1_offset
                    # Mirror x2 onto top-left coordinate system.
                    x2 = text1_length - x2
                    if x1 >= x2:
                        # Overlap detected.
                        return bisect_split_diffs(text1, text2, x1, y1)

    # Number of diffs equals number of characters, no commonality at all.
    return [Diff(Ops.DELETE, text1), Diff(Ops.INSERT, text2)]

def bisect_split_diffs(text1, text2, x, y):
    """Given the location of the 'middle snake', split the diff in two parts
    and recurse.

    Args:
        text1: Old string to be diffed.
        text2: New string to be diffed.
        x: Index of split point in text1.
        y: Index of split point in text2.

    Returns:
        List of diff tuples.
    """
    text1a = text1[:x]
    text2a = text2[:y]
    text1b = text1[x:]
    text2b = text2[y:]

    # Compute both diffs serially.
    diffs = myers_diffs(text1a, text2a, False)
    diffsb = myers_diffs(text1b, text2b, False)

    return diffs + diffsb

def lines_to_chars(text1, text2):
    """Split two texts into a list of strings.  Reduce the texts to a string
    of dicts where each Unicode character represents one line.

    Args:
        text1: First string.
        text2: Second string.

    Returns:
        Three element tuple, containing the encoded text1, the encoded text2 and
        the list of unique strings.  The zeroth element of the list of unique
        strings is intentionally blank.
    """
    line_list = []   # e.g. line_list[4] == "Hello\n"
    line_dict = {}   # e.g. line_dict["Hello\n"] == 4

    # "\x00" is a valid character, but various debuggers don't like it.
    # So we'll insert a junk entry to avoid generating a null character.
    line_list.append('')

    def lines_to_chars_munge(text):
        """Split a text into a list of strings.  Reduce the texts to a string
        of dicts where each Unicode character represents one line.
        Modifies line_list and lineHash through being a closure.

        Args:
            text: String to encode.

        Returns:
            Encoded string.
        """
        chars = []
        # Walk the text, pulling out a substring for each line.
        # text.split('\n') would would temporarily double our memory footprint.
        # Modifying text would create many large strings to garbage collect.
        line_start = 0
        line_end = -1
        while line_end < len(text) - 1:
            line_end = text.find('\n', line_start)
            if line_end == -1:
                line_end = len(text) - 1
            line = text[line_start:line_end + 1]
            line_start = line_end + 1

            if line in line_dict:
                chars.append(chr(line_dict[line]))
            else:
                line_list.append(line)
                line_dict[line] = len(line_list) - 1
                chars.append(chr(len(line_list) - 1))
        return ''.join(chars)

    chars1 = lines_to_chars_munge(text1)
    chars2 = lines_to_chars_munge(text2)
    return (chars1, chars2, line_list)

def common_prefix_length(text1, text2):
    """Determine the common prefix of two strings.

    Args:
        text1: First string.
        text2: Second string.

    Returns:
        The number of characters common to the start of each string.
    """
    # Quick check for common null cases.
    if not text1 or not text2 or text1[0] != text2[0]:
        return 0
    # Binary search.
    # Performance analysis: http://neil.fraser.name/news/2007/10/09/
    pointermin = 0
    pointermax = min(len(text1), len(text2))
    pointermid = pointermax
    pointerstart = 0
    while pointermin < pointermid:
        if text1[pointerstart:pointermid] == text2[pointerstart:pointermid]:
            pointermin = pointermid
            pointerstart = pointermin
        else:
            pointermax = pointermid
        pointermid = (pointermax - pointermin) // 2 + pointermin
    return pointermid

def common_suffix_length(text1, text2):
    """Determine the common suffix of two strings.

    Args:
        text1: First string.
        text2: Second string.

    Returns:
        The number of characters common to the end of each string.
    """
    # Quick check for common null cases.
    if not text1 or not text2 or text1[-1] != text2[-1]:
        return 0
    # Binary search.
    # Performance analysis: http://neil.fraser.name/news/2007/10/09/
    pointermin = 0
    pointermax = min(len(text1), len(text2))
    pointermid = pointermax
    pointerend = 0
    while pointermin < pointermid:
        if (text1[-pointermid:len(text1) - pointerend] ==
                text2[-pointermid:len(text2) - pointerend]):
            pointermin = pointermid
            pointerend = pointermin
        else:
            pointermax = pointermid
        pointermid = (pointermax - pointermin) // 2 + pointermin
    return pointermid

def common_overlap(text1, text2):
    """Determine if the suffix of one string is the prefix of another.

    Args:
        text1 First string.
        text2 Second string.

    Returns:
        The number of characters common to the end of the first
        string and the start of the second string.
    """
    # Cache the text lengths to prevent multiple calls.
    text1_length = len(text1)
    text2_length = len(text2)
    # Eliminate the null case.
    if text1_length == 0 or text2_length == 0:
        return 0
    # Truncate the longer string.
    if text1_length > text2_length:
        text1 = text1[-text2_length:]
    elif text1_length < text2_length:
        text2 = text2[:text1_length]
    text_length = min(text1_length, text2_length)
    # Quick check for the worst case.
    if text1 == text2:
        return text_length

    # Start by looking for a single character match
    # and increase length until no match is found.
    # Performance analysis: http://neil.fraser.name/news/2010/11/04/
    best = 0
    length = 1
    while True:
        pattern = text1[-length:]
        found = text2.find(pattern)
        if found == -1:
            return best
        length += found
        if found == 0 or text1[-length:] == text2[:length]:
            best = length
            length += 1

def cleanup_semantic(diffs):
    """Reduce the number of edits by eliminating semantically trivial
    equalities.

    Args:
        diffs: List of diff tuples.
    """
    changes = False
    equalities = []  # Stack of indices where equalities are found.
    lastequality = None  # Always equal to diffs[equalities[-1]].text
    pointer = 0  # Index of current position.
    # Number of chars that changed prior to the equality.
    (length_insertions1, length_deletions1) = (0, 0)
    # Number of chars that changed after the equality.
    (length_insertions2, length_deletions2) = (0, 0)
    while pointer < len(diffs):
        if diffs[pointer].op == Ops.EQUAL:  # Equality found.
            equalities.append(pointer)
            (length_insertions1, length_insertions2) = (length_insertions2, 0)
            (length_deletions1, length_deletions2) = (length_deletions2, 0)
            lastequality = diffs[pointer].text
        else:  # An insertion or deletion.
            if diffs[pointer].op == Ops.INSERT:
                length_insertions2 += len(diffs[pointer].text)
            else:
                length_deletions2 += len(diffs[pointer].text)
            # Eliminate an equality that is smaller or equal to the edits on both
            # sides of it.
            if (lastequality and (len(lastequality) <=
                    max(length_insertions1, length_deletions1)) and
                    (len(lastequality) <= max(length_insertions2, length_deletions2))):
                # Duplicate record.
                diffs.insert(equalities[-1], Diff(Ops.DELETE, lastequality))
                # Change second copy to insert.
                diffs[equalities[-1] + 1] = diffs[equalities[-1] + 1]._replace(op=Ops.INSERT)
                # Throw away the equality we just deleted.
                equalities.pop()
                # Throw away the previous equality (it needs to be reevaluated).
                if len(equalities):
                    equalities.pop()
                if len(equalities):
                    pointer = equalities[-1]
                else:
                    pointer = -1
                # Reset the counters.
                length_insertions1, length_deletions1 = 0, 0
                length_insertions2, length_deletions2 = 0, 0
                lastequality = None
                changes = True
        pointer += 1

    # Normalize the diff.
    if changes:
        cleanup_merge(diffs)
    cleanup_semantic_lossless(diffs)

    # Find any overlaps between deletions and insertions.
    # e.g: <del>abcxxx</del><ins>xxxdef</ins>
    #   -> <del>abc</del>xxx<ins>def</ins>
    # e.g: <del>xxxabc</del><ins>defxxx</ins>
    #   -> <ins>def</ins>xxx<del>abc</del>
    # Only extract an overlap if it is as big as the edit ahead or behind it.
    pointer = 1
    while pointer < len(diffs):
        if (diffs[pointer - 1].op == Ops.DELETE and
                diffs[pointer].op == Ops.INSERT):
            deletion = diffs[pointer - 1].text
            insertion = diffs[pointer].text
            overlap_length1 = common_overlap(deletion, insertion)
            overlap_length2 = common_overlap(insertion, deletion)
            if overlap_length1 >= overlap_length2:
                if (overlap_length1 >= len(deletion) / 2.0 or
                        overlap_length1 >= len(insertion) / 2.0):
                    # Overlap found.  Insert an equality and trim the surrounding edits.
                    diffs.insert(pointer, Diff(Ops.EQUAL, insertion[:overlap_length1]))
                    diffs[pointer - 1] = Diff(Ops.DELETE, deletion[:len(deletion) - overlap_length1])
                    diffs[pointer + 1] = Diff(Ops.INSERT, insertion[overlap_length1:])
                    pointer += 1
            else:
                if (overlap_length2 >= len(deletion) / 2.0 or
                        overlap_length2 >= len(insertion) / 2.0):
                    # Reverse overlap found.
                    # Insert an equality and swap and trim the surrounding edits.
                    diffs.insert(pointer, Diff(Ops.EQUAL, deletion[:overlap_length2]))
                    diffs[pointer - 1] = Diff(Ops.INSERT, insertion[:len(insertion) - overlap_length2])
                    diffs[pointer + 1] = Diff(Ops.DELETE, deletion[overlap_length2:])
                    pointer += 1
            pointer += 1
        pointer += 1

def cleanup_semantic_lossless(diffs):
    """Look for single edits surrounded on both sides by equalities
    which can be shifted sideways to align the edit to a word boundary.
    e.g: The c<ins>at c</ins>ame. -> The <ins>cat </ins>came.

    Args:
        diffs: List of diff tuples.
    """

    def cleanup_semantic_score(one, two):
        """Given two strings, compute a score representing whether the
        internal boundary falls on logical boundaries.
        Scores range from 6 (best) to 0 (worst).
        Closure, but does not reference any external variables.

        Args:
            one: First string.
            two: Second string.

        Returns:
            The score.
        """
        if not one or not two:
            # Edges are the best.
            return 6

        # Each port of this function behaves slightly differently due to
        # subtle differences in each language's definition of things like
        # 'whitespace'.  Since this function's purpose is largely cosmetic,
        # the choice has been made to use each language's native features
        # rather than force total conformity.
        char1 = one[-1]
        char2 = two[0]
        non_alpha_numeric_1 = not char1.isalnum()
        non_alpha_numeric_2 = not char2.isalnum()
        whitespace1 = non_alpha_numeric_1 and char1.isspace()
        whitespace2 = non_alpha_numeric_2 and char2.isspace()
        line_break_1 = whitespace1 and (char1 == "\r" or char1 == "\n")
        line_break_2 = whitespace2 and (char2 == "\r" or char2 == "\n")
        blank_line_1 = line_break_1 and BLANK_LINE_END.search(one)
        blank_line_2 = line_break_2 and BLANK_LINE_START.match(two)

        if blank_line_1 or blank_line_2:
            # Five points for blank lines.
            return 5
        elif line_break_1 or line_break_2:
            # Four points for line breaks.
            return 4
        elif non_alpha_numeric_1 and not whitespace1 and whitespace2:
            # Three points for end of sentences.
            return 3
        elif whitespace1 or whitespace2:
            # Two points for whitespace.
            return 2
        elif non_alpha_numeric_1 or non_alpha_numeric_2:
            # One point for non-alphanumeric.
            return 1
        return 0

    pointer = 1
    # Intentionally ignore the first and last element (don't need checking).
    while pointer < len(diffs) - 1:
        if (diffs[pointer - 1].op == Ops.EQUAL and
                diffs[pointer + 1].op == Ops.EQUAL):
            # This is a single edit surrounded by equalities.
            equality1 = diffs[pointer - 1].text
            edit = diffs[pointer].text
            equality2 = diffs[pointer + 1].text

            # First, shift the edit as far left as possible.
            common_offset = common_suffix_length(equality1, edit)
            if common_offset:
                common_string = edit[-common_offset:]
                equality1 = equality1[:-common_offset]
                edit = common_string + edit[:-common_offset]
                equality2 = common_string + equality2

            # Second, step character by character right, looking for the best fit.
            best_equality_1 = equality1
            best_edit = edit
            best_equality_2 = equality2
            best_score = (cleanup_semantic_score(equality1, edit) + cleanup_semantic_score(edit, equality2))
            while edit and equality2 and edit[0] == equality2[0]:
                equality1 += edit[0]
                edit = edit[1:] + equality2[0]
                equality2 = equality2[1:]
                score = (cleanup_semantic_score(equality1, edit) + cleanup_semantic_score(edit, equality2))
                # The >= encourages trailing rather than leading whitespace on edits.
                if score >= best_score:
                    best_score = score
                    best_equality_1 = equality1
                    best_edit = edit
                    best_equality_2 = equality2

            if diffs[pointer - 1].text != best_equality_1:
                # We have an improvement, save it back to the diff.
                if best_equality_1:
                    diffs[pointer - 1] = diffs[pointer - 1]._replace(text=best_equality_1)
                else:
                    del diffs[pointer - 1]
                    pointer -= 1
                diffs[pointer] = diffs[pointer]._replace(text=best_edit)
                if best_equality_2:
                    diffs[pointer + 1] = diffs[pointer + 1]._replace(text=best_equality_2)
                else:
                    del diffs[pointer + 1]
                    pointer -= 1
        pointer += 1

def cleanup_efficiency(diffs):
    """Reduce the number of edits by eliminating operationally trivial
    equalities.

    Args:
        diffs: List of diff tuples.
    """
    changes = False
    equalities = []  # Stack of indices where equalities are found.
    lastequality = None  # Always equal to diffs[equalities[-1]].text
    pointer = 0  # Index of current position.
    pre_ins = False  # Is there an insertion operation before the last equality.
    pre_del = False  # Is there a deletion operation before the last equality.
    post_ins = False  # Is there an insertion operation after the last equality.
    post_del = False  # Is there a deletion operation after the last equality.
    while pointer < len(diffs):
        if diffs[pointer].op == Ops.EQUAL:  # Equality found.
            if (len(diffs[pointer].text) < DIFF_EDIT_COST and
                    (post_ins or post_del)):
                # Candidate found.
                equalities.append(pointer)
                pre_ins = post_ins
                pre_del = post_del
                lastequality = diffs[pointer].text
            else:
                # Not a candidate, and can never become one.
                equalities = []
                lastequality = None

            post_ins = post_del = False
        else:  # An insertion or deletion.
            if diffs[pointer].op == Ops.DELETE:
                post_del = True
            else:
                post_ins = True

            # Five types to be split:
            # <ins>A</ins><del>B</del>XY<ins>C</ins><del>D</del>
            # <ins>A</ins>X<ins>C</ins><del>D</del>
            # <ins>A</ins><del>B</del>X<ins>C</ins>
            # <ins>A</del>X<ins>C</ins><del>D</del>
            # <ins>A</ins><del>B</del>X<del>C</del>

            if lastequality and ((pre_ins and pre_del and post_ins and post_del) or
                                                     ((len(lastequality) < DIFF_EDIT_COST / 2) and
                                                        (pre_ins + pre_del + post_ins + post_del) == 3)):
                # Duplicate record.
                diffs.insert(equalities[-1], Diff(Ops.DELETE, lastequality))
                # Change second copy to insert.
                diffs[equalities[-1] + 1] = Diff(Ops.INSERT, diffs[equalities[-1] + 1].text)
                equalities.pop()  # Throw away the equality we just deleted.
                lastequality = None
                if pre_ins and pre_del:
                    # No changes made which could affect previous entry, keep going.
                    post_ins = post_del = True
                    equalities = []
                else:
                    if len(equalities):
                        equalities.pop()  # Throw away the previous equality.
                    if len(equalities):
                        pointer = equalities[-1]
                    else:
                        pointer = -1
                    post_ins = post_del = False
                changes = True
        pointer += 1

    if changes:
        cleanup_merge(diffs)

def cleanup_merge(diffs):
    """Reorder and merge like edit sections.  Merge equalities.
    Any edit section can move as long as it doesn't cross an equality.

    Args:
        diffs: List of diff tuples.
    """
    diffs.append(Diff(Ops.EQUAL, ''))  # Add a dummy entry at the end.
    pointer = 0
    count_delete = 0
    count_insert = 0
    text_delete = ''
    text_insert = ''
    while pointer < len(diffs):
        if diffs[pointer].op == Ops.INSERT:
            count_insert += 1
            text_insert += diffs[pointer].text
            pointer += 1
        elif diffs[pointer].op == Ops.DELETE:
            count_delete += 1
            text_delete += diffs[pointer].text
            pointer += 1
        elif diffs[pointer].op == Ops.EQUAL:
            # Upon reaching an equality, check for prior redundancies.
            if count_delete + count_insert > 1:
                if count_delete != 0 and count_insert != 0:
                    # Factor out any common prefixies.
                    common_length = common_prefix_length(text_insert, text_delete)
                    if common_length != 0:
                        x = pointer - count_delete - count_insert - 1
                        if x >= 0 and diffs[x].op == Ops.EQUAL:
                            diffs[x] = diffs[x]._replace(text=(diffs[x].text + text_insert[:common_length]))
                        else:
                            diffs.insert(0, Diff(Ops.EQUAL, text_insert[:common_length]))
                            pointer += 1
                        text_insert = text_insert[common_length:]
                        text_delete = text_delete[common_length:]
                    # Factor out any common suffixies.
                    common_length = common_suffix_length(text_insert, text_delete)
                    if common_length != 0:
                        diffs[pointer] = diffs[pointer]._replace(text=(
                            text_insert[-common_length:] + diffs[pointer].text
                        ))
                        text_insert = text_insert[:-common_length]
                        text_delete = text_delete[:-common_length]
                # Delete the offending records and add the merged ones.
                if count_delete == 0:
                    diffs[pointer - count_insert : pointer] = [Diff(Ops.INSERT, text_insert)]
                elif count_insert == 0:
                    diffs[pointer - count_delete : pointer] = [Diff(Ops.DELETE, text_delete)]
                else:
                    diffs[pointer - count_delete - count_insert : pointer] = [
                            Diff(Ops.DELETE, text_delete),
                            Diff(Ops.INSERT, text_insert)]
                pointer = pointer - count_delete - count_insert + 1
                if count_delete != 0:
                    pointer += 1
                if count_insert != 0:
                    pointer += 1
            elif pointer != 0 and diffs[pointer - 1].op == Ops.EQUAL:
                # Merge this equality with the previous one.
                diffs[pointer - 1] = diffs[pointer - 1]._replace(text=(
                    diffs[pointer - 1].text + diffs[pointer].text
                ))
                del diffs[pointer]
            else:
                pointer += 1

            count_insert = 0
            count_delete = 0
            text_delete = ''
            text_insert = ''

    if diffs[-1].text == '':
        diffs.pop()  # Remove the dummy entry at the end.

    # Second pass: look for single edits surrounded on both sides by equalities
    # which can be shifted sideways to eliminate an equality.
    # e.g: A<ins>BA</ins>C -> <ins>AB</ins>AC
    changes = False
    pointer = 1
    # Intentionally ignore the first and last element (don't need checking).
    while pointer < len(diffs) - 1:
        if (diffs[pointer - 1].op == Ops.EQUAL and
                diffs[pointer + 1].op == Ops.EQUAL):
            # This is a single edit surrounded by equalities.
            if diffs[pointer].text.endswith(diffs[pointer - 1].text):
                # Shift the edit over the previous equality.
                diffs[pointer] = diffs[pointer]._replace(text=(
                    diffs[pointer - 1].text + diffs[pointer].text[:-len(diffs[pointer - 1].text)]
                ))
                diffs[pointer + 1] = diffs[pointer + 1]._replace(text=(
                    diffs[pointer - 1].text + diffs[pointer + 1].text
                ))
                del diffs[pointer - 1]
                changes = True
            elif diffs[pointer].text.startswith(diffs[pointer + 1].text):
                # Shift the edit over the next equality.
                diffs[pointer - 1] = diffs[pointer - 1]._replace(text=(
                    diffs[pointer - 1].text + diffs[pointer + 1].text
                ))
                diffs[pointer] = diffs[pointer]._replace(text=(
                    diffs[pointer].text[len(diffs[pointer + 1].text):] + diffs[pointer + 1].text
                ))
                del diffs[pointer + 1]
                changes = True
        pointer += 1

    # If shifts were made, the diff needs reordering and another shift sweep.
    if changes:
        cleanup_merge(diffs)
