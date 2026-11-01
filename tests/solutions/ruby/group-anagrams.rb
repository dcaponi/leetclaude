# @param {String[]} strs
# @return {String[][]}
def group_anagrams(strs)
  strs.group_by { |s| s.chars.sort.join }.values
end
