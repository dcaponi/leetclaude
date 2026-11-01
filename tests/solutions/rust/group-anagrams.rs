use std::collections::HashMap;

impl Solution {
    pub fn group_anagrams(strs: Vec<String>) -> Vec<Vec<String>> {
        let mut groups: HashMap<String, Vec<String>> = HashMap::new();
        for s in strs {
            let mut key: Vec<char> = s.chars().collect();
            key.sort_unstable();
            groups.entry(key.into_iter().collect()).or_default().push(s);
        }
        groups.into_values().collect()
    }
}
