impl Solution {
    pub fn find_median_sorted_arrays(nums1: Vec<i32>, nums2: Vec<i32>) -> f64 {
        let mut merged = Vec::with_capacity(nums1.len() + nums2.len());
        let (mut i, mut j) = (0, 0);
        while i < nums1.len() && j < nums2.len() {
            if nums1[i] <= nums2[j] {
                merged.push(nums1[i]);
                i += 1;
            } else {
                merged.push(nums2[j]);
                j += 1;
            }
        }
        merged.extend_from_slice(&nums1[i..]);
        merged.extend_from_slice(&nums2[j..]);
        let n = merged.len();
        if n % 2 == 1 {
            merged[n / 2] as f64
        } else {
            (merged[n / 2 - 1] as f64 + merged[n / 2] as f64) / 2.0
        }
    }
}
