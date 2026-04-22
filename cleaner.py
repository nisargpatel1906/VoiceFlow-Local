"""
VoiceFlow Local - Text Cleaner Module

Cleans and formats raw Whisper transcription output.
Handles filler words, self-corrections, formatting, and voice commands.
"""

import re
import config


class TextCleaner:
    """
    Cleans raw transcription text for polished output.

    Applies filler word removal, self-correction handling,
    sentence formatting, and voice command processing.
    """

    # Voice command mappings
    VOICE_COMMANDS = {
        'new line': '\n',
        'new paragraph': '\n\n',
        'comma': ',',
        'period': '.',
        'full stop': '.',
        'question mark': '?',
        'exclamation point': '!',
        'colon': ':',
        'semicolon': ';',
        'dash': '—',
        'open quote': '"',
        'close quote': '"',
        'open paren': '(',
        'close paren': ')',
    }

    # Self-correction patterns
    CORRECTION_PATTERNS = [
        r'\bno wait\b',
        r'\bactually\b',
        r'\bI mean\b',
        r'\bsorry\b',
        r'\bwait\b',
    ]

    def __init__(self):
        """Initialize the text cleaner with config settings."""
        self.filler_words = config.FILLER_WORDS
        self.remove_fillers_enabled = config.REMOVE_FILLERS
        self.fix_self_corrections_enabled = getattr(config, 'FIX_SELF_CORRECTIONS', True)
        self.auto_capitalize_enabled = getattr(config, 'AUTO_CAPITALIZE', True)
        self.voice_commands_enabled = getattr(config, 'ENABLE_VOICE_COMMANDS', True)

    def deduplicate_chunks(self, text: str) -> str:
        """
        Remove repeated 1-4 word sequences caused by chunk overlap.

        Only removes the second occurrence when the same sequence repeats
        within a short local window, which keeps normal repetition intact.
        """
        words = text.split()
        if len(words) < 2:
            return text.strip()

        index = 0
        while index < len(words):
            removed = False
            max_sequence = min(4, (len(words) - index) // 2 or 1)
            for sequence_len in range(max_sequence, 0, -1):
                first_sequence = words[index:index + sequence_len]
                if len(first_sequence) < sequence_len:
                    continue

                max_second_start = min(len(words) - sequence_len, index + 8)
                for second_start in range(index + sequence_len, max_second_start + 1):
                    if words[second_start:second_start + sequence_len] != first_sequence:
                        continue

                    if (
                        sequence_len == 1
                        and second_start == index + 2
                        and words[index + 1].lower() == "to"
                    ):
                        del words[index + 1:second_start + sequence_len]
                    else:
                        del words[second_start:second_start + sequence_len]
                    removed = True
                    break

                if removed:
                    break

            if not removed:
                index += 1

        return " ".join(words).strip()

    def is_duplicate_of_previous(self, new_chunk: str, previous_transcript: str) -> bool:
        """
        Return True when a whole chunk is already present in the recent transcript tail.
        """
        new_words = new_chunk.split()
        if not new_words:
            return False

        previous_words = previous_transcript.split()
        if not previous_words:
            return False

        tail_words = previous_words[-20:]
        if len(new_words) > len(tail_words):
            return False

        lowered_new = [word.lower() for word in new_words]
        lowered_tail = [word.lower() for word in tail_words]
        window_size = len(lowered_new)

        for start in range(len(lowered_tail) - window_size + 1):
            if lowered_tail[start:start + window_size] == lowered_new:
                return True
        return False

    def remove_fillers(self, text):
        """
        Remove filler words from text (word-boundary aware).

        Args:
            text: Raw transcription text.

        Returns:
            str: Text with filler words removed.

        Examples:
            >>> cleaner = TextCleaner()
            >>> cleaner.remove_fillers("um like you know hello")
            'hello'
            >>> cleaner.remove_fillers("I like the movie")  # 'like' in 'likewise' safe
            'I the movie'
        """
        if not self.remove_fillers_enabled:
            return text

        result = text
        for filler in self.filler_words:
            # Word-boundary regex: \b ensures 'like' doesn't match 'likewise'
            pattern = r'\b' + re.escape(filler) + r'\b'
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)

        # Clean up extra spaces from removal
        result = re.sub(r'\s+', ' ', result)
        return result.strip()

    def fix_self_corrections(self, text):
        """
        Handle self-corrections by removing text before correction markers.

        Args:
            text: Raw transcription text.

        Returns:
            str: Text with self-corrections resolved.

        Examples:
            >>> cleaner = TextCleaner()
            >>> cleaner.fix_self_corrections("meet at 5pm no wait 6pm")
            'meet at 6pm'
            >>> cleaner.fix_self_corrections("I want red, actually blue one")
            'I want blue one'
        """
        result = text

        for pattern in self.CORRECTION_PATTERNS:
            # Find correction marker and remove everything before it (in same clause)
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                marker_pos = match.start()
                # Find the start of current clause (look for comma or start of string)
                clause_start = result.rfind(',', 0, marker_pos)
                if clause_start == -1:
                    clause_start = 0
                else:
                    clause_start += 1  # Skip the comma

                # Remove the corrected portion
                result = result[:clause_start] + result[marker_pos + len(match.group()):]

        # Clean up any resulting double spaces
        result = re.sub(r'\s+', ' ', result)
        return result.strip()

    def format_sentence(self, text):
        """
        Format text with proper capitalization and punctuation.

        Args:
            text: Raw transcription text.

        Returns:
            str: Properly formatted sentence.

        Examples:
            >>> cleaner = TextCleaner()
            >>> cleaner.format_sentence("hello world")
            'Hello world.'
            >>> cleaner.format_sentence("  double   space  ")
            'Double space.'
            >>> cleaner.format_sentence("already has period.")
            'Already has period.'
        """
        if not text:
            return ''

        # Strip whitespace
        text = text.strip()

        # Fix double spaces
        text = re.sub(r'\s+', ' ', text)

        # Capitalize first letter
        if text:
            text = text[0].upper() + text[1:] if len(text) > 1 else text.upper()

        # Add period if no ending punctuation
        if text and text[-1] not in '.!?\n':
            text += '.'

        return text

    def handle_voice_commands(self, text):
        """
        Process voice commands for punctuation and formatting.

        Args:
            text: Raw transcription text containing voice commands.

        Returns:
            str: Processed text with commands executed, or DELETE_LAST token.

        Examples:
            >>> cleaner = TextCleaner()
            >>> cleaner.handle_voice_commands("hello comma how are you")
            'hello, how are you'
            >>> cleaner.handle_voice_commands("first line new line second line")
            'first line\nsecond line'
            >>> cleaner.handle_voice_commands("delete that")
            'DELETE_LAST'
        """
        result = text.lower()

        # Check for delete command
        if 'delete that' in result or 'delete last' in result:
            return 'DELETE_LAST'

        # Replace voice commands with actual punctuation
        for command, replacement in self.VOICE_COMMANDS.items():
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(command) + r'\b'
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Clean up spaces around punctuation (except newlines)
        result = re.sub(r'\s+,\s*', ', ', result)
        result = re.sub(r'\s+\.\s*', '. ', result)
        result = re.sub(r'\s+\?\s*', '? ', result)
        result = re.sub(r'\s+!\s*', '! ', result)

        return result.strip()

    def clean(self, text):
        """
        Run all cleaning steps in order.

        Order of operations:
        1. Handle voice commands (punctuation insertion)
        2. Fix self-corrections
        3. Remove filler words
        4. Format sentence (capitalization, period)

        Args:
            text: Raw transcription text.

        Returns:
            str: Fully cleaned and formatted text.

        Example:
            >>> cleaner = TextCleaner()
            >>> cleaner.clean("um like meet at 5 no wait 6pm comma please")
            'Meet at 6pm, please.'
        """
        if not text:
            return ''

        # Step 1: Remove chunk-boundary duplicates first.
        text = self.deduplicate_chunks(text)

        # Step 2: Handle voice commands first (they add punctuation)
        if self.voice_commands_enabled:
            text = self.handle_voice_commands(text)

        # Check for delete command result
        if text == 'DELETE_LAST':
            return 'DELETE_LAST'

        # Step 3: Fix self-corrections
        if self.fix_self_corrections_enabled:
            text = self.fix_self_corrections(text)

        # Step 4: Remove filler words
        text = self.remove_fillers(text)

        # Step 5: Format sentence
        if self.auto_capitalize_enabled:
            text = self.format_sentence(text)
        else:
            text = re.sub(r'\s+', ' ', text).strip()

        return text


# =============================================================================
# UNIT TESTS (run with: python cleaner.py)
# =============================================================================
if __name__ == '__main__':
    cleaner = TextCleaner()

    print("=" * 60)
    print("TextCleaner Unit Tests")
    print("=" * 60)

    # Test 1: remove_fillers
    print("\n1. remove_fillers():")
    test_cases = [
        ("um like you know hello world", "Like you know hello world."),
        ("I um think like it's good", "I think it's good."),
        ("no fillers here", "No fillers here."),
    ]
    for input_text, _ in test_cases:
        result = cleaner.remove_fillers(input_text)
        print(f"   Input:  '{input_text}'")
        print(f"   Output: '{result}'")

    # Test 2: fix_self_corrections
    print("\n2. fix_self_corrections():")
    test_cases = [
        "meet at 5pm no wait 6pm",
        "I want the red one actually the blue one",
        "go to the store I mean the mall",
        "sorry what I meant was hello",
    ]
    for input_text in test_cases:
        result = cleaner.fix_self_corrections(input_text)
        print(f"   Input:  '{input_text}'")
        print(f"   Output: '{result}'")

    # Test 3: format_sentence
    print("\n3. format_sentence():")
    test_cases = [
        "hello world",
        "  double   space  ",
        "already has period.",
        "what about this?",
    ]
    for input_text in test_cases:
        result = cleaner.format_sentence(input_text)
        print(f"   Input:  '{input_text}'")
        print(f"   Output: '{result}'")

    # Test 4: handle_voice_commands
    print("\n4. handle_voice_commands():")
    test_cases = [
        "hello comma how are you",
        "first line new line second line",
        "new paragraph start fresh",
        "delete that",
        "say period now period",
    ]
    for input_text in test_cases:
        result = cleaner.handle_voice_commands(input_text)
        print(f"   Input:  '{input_text}'")
        print(f"   Output: '{result}'")

    # Test 5: Full clean pipeline
    print("\n5. clean() - Full pipeline:")
    test_cases = [
        "um like meet at 5 no wait 6pm comma please",
        "actually I want uh new line hello world",
        "delete that",
    ]
    for input_text in test_cases:
        result = cleaner.clean(input_text)
        print(f"   Input:  '{input_text}'")
        print(f"   Output: '{result}'")

    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)
