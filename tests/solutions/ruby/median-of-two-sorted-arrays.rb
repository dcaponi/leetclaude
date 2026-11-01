# @param {Integer[]} nums1
# @param {Integer[]} nums2
# @return {Float}
def find_median_sorted_arrays(nums1, nums2)
  merged = []
  i = j = 0
  while i < nums1.size && j < nums2.size
    if nums1[i] <= nums2[j]
      merged << nums1[i]; i += 1
    else
      merged << nums2[j]; j += 1
    end
  end
  merged.concat(nums1[i..]).concat(nums2[j..])
  n = merged.size
  n.odd? ? merged[n / 2] : (merged[n / 2 - 1] + merged[n / 2]) / 2.0
end
