public class Solution {
    public double FindMedianSortedArrays(int[] nums1, int[] nums2) {
        int[] merged = new int[nums1.Length + nums2.Length];
        int i = 0, j = 0, k = 0;
        while (i < nums1.Length && j < nums2.Length) {
            merged[k++] = nums1[i] <= nums2[j] ? nums1[i++] : nums2[j++];
        }
        while (i < nums1.Length) merged[k++] = nums1[i++];
        while (j < nums2.Length) merged[k++] = nums2[j++];
        int n = merged.Length;
        if (n % 2 == 1) return merged[n / 2];
        return (merged[n / 2 - 1] + merged[n / 2]) / 2.0;
    }
}
