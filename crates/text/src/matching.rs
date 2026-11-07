//! Shared literal multi-pattern search and bounded compiled-regex reuse.
use aho_corasick::{AhoCorasick, AhoCorasickBuilder, MatchKind};
use regex::{Regex, RegexBuilder};
use std::{cell::RefCell, collections::VecDeque};

/// A literal hit with byte offsets into the searched text and its input pattern index.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LiteralMatch {
    pub pattern: usize,
    pub start: usize,
    pub end: usize,
}

/// Compiles a leftmost-longest multi-pattern matcher, preserving pattern indices.
pub fn literal_matcher(patterns: &[&str], insensitive: bool) -> Result<AhoCorasick, aho_corasick::BuildError> {
    AhoCorasickBuilder::new().match_kind(MatchKind::LeftmostLongest).ascii_case_insensitive(insensitive).build(patterns)
}

/// Compiles a matcher that can report overlapping hits from every literal pattern.
pub fn overlapping_literal_matcher(patterns: &[&str], insensitive: bool) -> Result<AhoCorasick, aho_corasick::BuildError> {
    AhoCorasickBuilder::new().match_kind(MatchKind::Standard).ascii_case_insensitive(insensitive).build(patterns)
}

/// Compiles a byte matcher for arbitrary binary patterns.
pub fn overlapping_byte_matcher(patterns: &[&[u8]]) -> Result<AhoCorasick, aho_corasick::BuildError> {
    AhoCorasickBuilder::new().match_kind(MatchKind::Standard).build(patterns)
}

/// Finds non-overlapping matches using leftmost-longest selection.
pub fn find_literals(matcher: &AhoCorasick, haystack: &str) -> Vec<LiteralMatch> {
    matcher.find_iter(haystack).map(|m| LiteralMatch { pattern: m.pattern().as_usize(), start: m.start(), end: m.end() }).collect()
}

/// Finds all overlapping literal hits, ordered by pattern then start offset.
pub fn find_literals_overlapping(matcher: &AhoCorasick, haystack: &str) -> Vec<LiteralMatch> {
    let mut by_pattern = vec![Vec::new(); matcher.patterns_len()];
    for m in matcher.find_overlapping_iter(haystack) {
        if let Some(hits) = by_pattern.get_mut(m.pattern().as_usize()) {
            hits.push(LiteralMatch { pattern: m.pattern().as_usize(), start: m.start(), end: m.end() });
        }
    }
    by_pattern.into_iter().flatten().collect()
}

/// Finds every overlapping binary hit, ordered by pattern then start offset.
pub fn find_bytes_overlapping(matcher: &AhoCorasick, haystack: &[u8]) -> Vec<LiteralMatch> {
    find_bytes_overlapping_limited(matcher, haystack, usize::MAX)
}

/// Like [`find_bytes_overlapping`], with at most `per_pattern_limit` hits retained per pattern.
/// The full scan still runs, but result memory is bounded by patterns × limit.
pub fn find_bytes_overlapping_limited(matcher: &AhoCorasick, haystack: &[u8], per_pattern_limit: usize) -> Vec<LiteralMatch> {
    let mut by_pattern = vec![Vec::new(); matcher.patterns_len()];
    for m in matcher.find_overlapping_iter(haystack) {
        let pattern = m.pattern().as_usize();
        if let Some(hits) = by_pattern.get_mut(pattern) {
            if hits.len() < per_pattern_limit {
                hits.push(LiteralMatch { pattern, start: m.start(), end: m.end() });
            }
        }
    }
    by_pattern.into_iter().flatten().collect()
}

const CACHE_CAPACITY: usize = 32;
const MAX_CACHED_PATTERN: usize = 1024;
thread_local! {
    static REGEX_CACHE: RefCell<VecDeque<(String, bool, usize, usize, u32, Regex)>> = const { RefCell::new(VecDeque::new()) };
}

/// Returns a cached regex clone, compiling each key at most once while it remains in the
/// per-thread bounded FIFO cache. Oversized patterns are compiled but never retained.
pub fn cached_regex(pattern: &str, insensitive: bool) -> Result<Regex, regex::Error> {
    cached_regex_with_limits(pattern, insensitive, 1 << 20, 1 << 20, 250)
}

/// Same as [`cached_regex`], with explicit regex-automata and parser limits included in the key.
pub fn cached_regex_with_limits(
    pattern: &str,
    insensitive: bool,
    size_limit: usize,
    dfa_size_limit: usize,
    nest_limit: u32,
) -> Result<Regex, regex::Error> {
    if pattern.len() <= MAX_CACHED_PATTERN {
        if let Some(hit) = REGEX_CACHE.with(|cache| {
            let cache = cache.borrow();
            cache
                .iter()
                .find(|(p, i, s, d, n, _)| p == pattern && *i == insensitive && *s == size_limit && *d == dfa_size_limit && *n == nest_limit)
                .map(|(_, _, _, _, _, regex)| regex.clone())
        }) {
            return Ok(hit);
        }
    }
    let regex = RegexBuilder::new(pattern)
        .case_insensitive(insensitive)
        .size_limit(size_limit)
        .dfa_size_limit(dfa_size_limit)
        .nest_limit(nest_limit)
        .build()?;
    if pattern.len() <= MAX_CACHED_PATTERN {
        REGEX_CACHE.with(|cache| {
            let mut cache = cache.borrow_mut();
            if let Some(index) = cache
                .iter()
                .position(|(p, i, s, d, n, _)| p == pattern && *i == insensitive && *s == size_limit && *d == dfa_size_limit && *n == nest_limit)
            {
                cache.remove(index);
            }
            while cache.len() >= CACHE_CAPACITY {
                cache.pop_front();
            }
            cache.push_back((pattern.to_owned(), insensitive, size_limit, dfa_size_limit, nest_limit, regex.clone()));
        });
    }
    Ok(regex)
}

#[cfg(test)]
mod tests {
    use super::*;
    use proptest::prelude::*;

    fn naive(text: &str, patterns: &[String]) -> Vec<LiteralMatch> {
        let mut out = Vec::new();
        let mut at = 0;
        while at < text.len() {
            let best = patterns
                .iter()
                .enumerate()
                .filter_map(|(i, p)| text.get(at..).and_then(|tail| tail.starts_with(p).then_some((i, p.len()))))
                .max_by(|(left_index, left_len), (right_index, right_len)| left_len.cmp(right_len).then_with(|| right_index.cmp(left_index)));
            if let Some((pattern, len)) = best {
                out.push(LiteralMatch { pattern, start: at, end: at + len });
                at += len;
            } else {
                at += text[at..].chars().next().map_or(1, char::len_utf8);
            }
        }
        out
    }

    #[test]
    fn overlapping_matches_equal_per_pattern_naive_search() {
        let text = "ababa";
        let patterns = ["aba", "ba"];
        let matcher = overlapping_literal_matcher(&patterns, false).unwrap();
        let expected: Vec<_> = patterns
            .iter()
            .enumerate()
            .flat_map(|(pattern, needle)| {
                text.as_bytes().windows(needle.len()).enumerate().filter_map(move |(start, window)| {
                    (window == needle.as_bytes()).then_some(LiteralMatch { pattern, start, end: start + needle.len() })
                })
            })
            .collect();
        assert_eq!(find_literals_overlapping(&matcher, text), expected);
    }

    #[test]
    fn regex_cache_stays_bounded_and_skips_oversized_keys() {
        for i in 0..(CACHE_CAPACITY + 5) {
            cached_regex(&format!("a{{{i}}}"), false).unwrap();
        }
        REGEX_CACHE.with(|cache| assert_eq!(cache.borrow().len(), CACHE_CAPACITY));
        cached_regex(&"a".repeat(MAX_CACHED_PATTERN + 1), false).unwrap();
        REGEX_CACHE.with(|cache| assert_eq!(cache.borrow().len(), CACHE_CAPACITY));
    }

    proptest! {
        #[test]
        fn overlapping_byte_matches_equal_naive_search(haystack in prop::collection::vec(any::<u8>(), 0..100), patterns in prop::collection::vec(prop::collection::vec(any::<u8>(), 1..10), 1..8)) {
            let refs: Vec<_> = patterns.iter().map(Vec::as_slice).collect();
            let matcher = overlapping_byte_matcher(&refs).unwrap();
            let mut expected = Vec::new();
            for (pattern, needle) in patterns.iter().enumerate() {
                if needle.len() <= haystack.len() {
                    for start in 0..=haystack.len() - needle.len() {
                        if haystack.get(start..start + needle.len()) == Some(needle.as_slice()) {
                            expected.push(LiteralMatch { pattern, start, end: start + needle.len() });
                        }
                    }
                }
            }
            prop_assert_eq!(find_bytes_overlapping(&matcher, &haystack), expected);
        }
    }

    proptest! {
        #[test]
        fn leftmost_longest_matches_naive(text in "[a-c]{0,80}", pats in prop::collection::vec("[a-c]{1,8}", 1..8)) {
            let refs: Vec<_> = pats.iter().map(String::as_str).collect();
            let matcher = literal_matcher(&refs, false).unwrap();
            prop_assert_eq!(find_literals(&matcher, &text), naive(&text, &pats));
        }

        #[test]
        fn cached_regex_matches_fresh_compile(pattern in "[a-z]{1,8}", text in "[a-z]{0,80}", insensitive in any::<bool>()) {
            let got = cached_regex(&pattern, insensitive).unwrap();
            let expected = RegexBuilder::new(&pattern).case_insensitive(insensitive).build().unwrap();
            prop_assert_eq!(got.is_match(&text), expected.is_match(&text));
        }

        #[test]
        fn cached_limited_regex_matches_fresh_compile(pattern in "[a-z]{1,8}", text in "[a-z]{0,80}", insensitive in any::<bool>()) {
            let got = cached_regex_with_limits(&pattern, insensitive, 1 << 22, 1 << 22, 100).unwrap();
            let expected = RegexBuilder::new(&pattern).case_insensitive(insensitive).size_limit(1 << 22).dfa_size_limit(1 << 22).nest_limit(100).build().unwrap();
            prop_assert_eq!(got.is_match(&text), expected.is_match(&text));
        }
    }
}
