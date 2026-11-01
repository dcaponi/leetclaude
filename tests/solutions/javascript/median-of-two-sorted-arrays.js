/**
 * @param {number[]} nums1
 * @param {number[]} nums2
 * @return {number}
 */
var findMedianSortedArrays = function(nums1, nums2) {
    const merged = [];
    let i = 0, j = 0;
    while (i < nums1.length || j < nums2.length) {
        if (j >= nums2.length || (i < nums1.length && nums1[i] <= nums2[j])) merged.push(nums1[i++]);
        else merged.push(nums2[j++]);
    }
    const n = merged.length;
    return n % 2 ? merged[(n - 1) / 2] : (merged[n / 2 - 1] + merged[n / 2]) / 2;
};
