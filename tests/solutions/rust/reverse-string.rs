impl Solution {
    pub fn reverse_string(s: &mut Vec<char>) {
        if s.is_empty() {
            return;
        }
        let (mut i, mut j) = (0, s.len() - 1);
        while i < j {
            s.swap(i, j);
            i += 1;
            j -= 1;
        }
    }
}
