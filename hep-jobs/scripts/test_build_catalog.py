import unittest

from build_catalog import clean_url


class SourceUrlTests(unittest.TestCase):
    def test_ajo_bare_query_remains_distinct_from_old_empty_value_url(self):
        listing = 'https://academicjobsonline.org/ajo?joblst-0-0-2687-0-g-----'
        old_url = listing + '='
        self.assertEqual(clean_url(listing), listing)
        self.assertEqual(clean_url(old_url), old_url)
        self.assertNotEqual(clean_url(listing), clean_url(old_url))

    def test_standard_queries_keep_existing_normalization(self):
        source = 'https://example.edu/jobs?q=particle%20physics&empty=&utm_source=share&page=2#positions'
        expected = 'https://example.edu/jobs?q=particle+physics&empty=&page=2#positions'
        self.assertEqual(clean_url(source), expected)
        self.assertEqual(clean_url(expected), expected)


if __name__ == '__main__':
    unittest.main()
