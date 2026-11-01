# @param {Character[]} s
# @return {Void} Do not return anything, modify s in-place instead.
def reverse_string(s)
  l, r = 0, s.length - 1
  while l < r
    s[l], s[r] = s[r], s[l]
    l += 1
    r -= 1
  end
  nil
end
