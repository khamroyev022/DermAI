from django.test import SimpleTestCase

from apps.documents.services.chunking import PageText, chunk_pages
from apps.documents.services.text_cleaning import clean_text, has_meaningful_text


class TextCleaningTests(SimpleTestCase):
    def test_collapses_whitespace_and_joins_lines(self):
        raw = "Vitiligo   is a\nchronic  disorder.\n\n\n\nNext   paragraph.\r\n"
        self.assertEqual(clean_text(raw), "Vitiligo is a chronic disorder.\n\nNext paragraph.")

    def test_rejoins_hyphenated_words(self):
        self.assertEqual(clean_text("derma-\ntology is fun"), "dermatology is fun")

    def test_keeps_cyrillic_and_uzbek(self):
        raw = "Витилиго — это заболевание.\nO'zbek tili: teri kasalligi."
        self.assertEqual(clean_text(raw), "Витилиго — это заболевание. O'zbek tili: teri kasalligi.")

    def test_meaningful_text(self):
        self.assertFalse(has_meaningful_text("   \n  . . ."))
        self.assertTrue(has_meaningful_text("Vitiligo is a chronic skin disorder."))


class ChunkingTests(SimpleTestCase):
    def test_respects_size_and_never_splits_words(self):
        sentence = "Vitiligo causes depigmented patches on the skin. "
        page = PageText(1, sentence * 40)
        chunks = chunk_pages([page], chunk_size=200, chunk_overlap=40)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertLessEqual(len(chunk.text), 200)
            self.assertFalse(chunk.text.startswith(" "))
            self.assertTrue(chunk.text.endswith("."))
        self.assertEqual([c.chunk_index for c in chunks], list(range(len(chunks))))

    def test_overlap_repeats_trailing_sentence(self):
        page = PageText(1, "A first sentence here. Second sentence follows. Third one now. Fourth ends it.")
        chunks = chunk_pages([page], chunk_size=50, chunk_overlap=25)
        self.assertGreater(len(chunks), 1)
        # The start of chunk 2 should be found at the end of chunk 1 (overlap).
        first_sentence_of_second = chunks[1].text.split(". ")[0]
        self.assertIn(first_sentence_of_second, chunks[0].text)

    def test_page_range_tracked_across_pages(self):
        pages = [PageText(341, "Text on page three forty one. " * 5), PageText(342, "Continues on the next page. " * 5)]
        chunks = chunk_pages(pages, chunk_size=800, chunk_overlap=100)
        self.assertEqual(len(chunks), 1)
        self.assertEqual((chunks[0].page_start, chunks[0].page_end), (341, 342))

    def test_single_page_chunk_has_equal_bounds(self):
        chunks = chunk_pages([PageText(7, "Only one page of text here.")], chunk_size=800, chunk_overlap=100)
        self.assertEqual((chunks[0].page_start, chunks[0].page_end), (7, 7))

    def test_overlong_sentence_is_split_on_words(self):
        page = PageText(1, " ".join(f"w{i}" for i in range(300)))  # no punctuation at all
        chunks = chunk_pages([page], chunk_size=100, chunk_overlap=0)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(len(c.text) <= 100 for c in chunks))
        rebuilt = " ".join(c.text for c in chunks).split()
        self.assertEqual(rebuilt, [f"w{i}" for i in range(300)])

    def test_empty_pages_produce_no_chunks(self):
        self.assertEqual(chunk_pages([PageText(1, ""), PageText(2, "   ")], chunk_size=800, chunk_overlap=100), [])

    def test_custom_length_function(self):
        page = PageText(1, "one two three four five six seven eight nine ten. " * 10)
        token_len = lambda s: len(s.split())  # noqa: E731
        chunks = chunk_pages([page], chunk_size=25, chunk_overlap=5, length_fn=token_len)
        self.assertTrue(all(len(c.text.split()) <= 25 for c in chunks))

    def test_invalid_parameters(self):
        with self.assertRaises(ValueError):
            chunk_pages([], chunk_size=0, chunk_overlap=0)
        with self.assertRaises(ValueError):
            chunk_pages([], chunk_size=100, chunk_overlap=100)
