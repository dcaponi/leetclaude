func findMedianSortedArrays(nums1 []int, nums2 []int) float64 {
    merged := make([]int, 0, len(nums1)+len(nums2))
    merged = append(merged, nums1...)
    merged = append(merged, nums2...)
    sort.Ints(merged)
    n := len(merged)
    if n%2 == 1 {
        return float64(merged[n/2])
    }
    return float64(merged[n/2-1]+merged[n/2]) / 2.0
}
