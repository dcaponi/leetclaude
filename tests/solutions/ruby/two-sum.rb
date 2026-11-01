# @param {Integer[]} nums
# @param {Integer} target
# @return {Integer[]}
def two_sum(nums, target)
  seen = {}
  nums.each_with_index do |n, i|
    return [seen[target - n], i] if seen.key?(target - n)
    seen[n] = i
  end
  []
end
