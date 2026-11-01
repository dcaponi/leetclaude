function findMedianSortedArrays(nums1: number[], nums2: number[]): number {
    const merged: number[] = [];
    let i = 0, j = 0;
    while (i < nums1.length && j < nums2.length) {
        merged.push(nums1[i] <= nums2[j] ? nums1[i++] : nums2[j++]);
    }
    while (i < nums1.length) merged.push(nums1[i++]);
    while (j < nums2.length) merged.push(nums2[j++]);
    const mid = Math.floor(merged.length / 2);
    return merged.length % 2 === 1 ? merged[mid] : (merged[mid - 1] + merged[mid]) / 2;
};
