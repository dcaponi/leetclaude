# Definition for singly-linked list.
# class ListNode
#     attr_accessor :val, :next
#     def initialize(val = 0, _next = nil)
#         @val = val
#         @next = _next
#     end
# end
# @param {ListNode[]} lists
# @return {ListNode}
def merge_k_lists(lists)
  dummy = ListNode.new
  tail = dummy
  heads = lists.compact
  until heads.empty?
    k = (0...heads.size).min_by { |idx| heads[idx].val }
    tail.next = heads[k]
    tail = tail.next
    if heads[k].next
      heads[k] = heads[k].next
    else
      heads.delete_at(k)
    end
  end
  tail.next = nil
  dummy.next
end
