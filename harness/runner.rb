# LeetClaude Ruby harness. Usage: ruby runner.rb spec.json solution.rb
require 'json'
require 'set'

$stdout.sync = true
LG_M = "@@LG@@"
LG_ME = "@@LGE@@"

class ListNode
  attr_accessor :val, :next
  def initialize(val = 0, _next = nil)
    @val = val
    @next = _next
  end
end

class TreeNode
  attr_accessor :val, :left, :right
  def initialize(val = 0, left = nil, right = nil)
    @val = val
    @left = left
    @right = right
  end
end

def lg_emit(i, payload, err = false)
  $stdout.write("\n#{err ? LG_ME : LG_M}#{i}\t#{JSON.generate(payload)}\n")
end

def lg_seq?(t) = t.end_with?("[]") || t.start_with?("list<")
def lg_elem(t) = t.end_with?("[]") ? t[0...-2] : t[5...-1]

def lg_build_list(a)
  head = nil
  a.reverse_each { |v| head = ListNode.new(v, head) }
  head
end

def lg_build_tree(a)
  return nil if a.empty? || a[0].nil?
  root = TreeNode.new(a[0])
  q = [root]
  i = 1
  while !q.empty? && i < a.size
    node = q.shift
    if i < a.size && !a[i].nil?
      node.left = TreeNode.new(a[i]); q << node.left
    end
    i += 1
    if i < a.size && !a[i].nil?
      node.right = TreeNode.new(a[i]); q << node.right
    end
    i += 1
  end
  root
end

def lg_to(t, v)
  return nil if v.nil?
  return lg_build_list(v) if t == "ListNode"
  return lg_build_tree(v) if t == "TreeNode"
  return v.map { |x| lg_to(lg_elem(t), x) } if lg_seq?(t)
  return v.to_f if t == "double"
  v
end

def lg_from(t, r)
  if r.nil?
    return %w[ListNode TreeNode].include?(t) ? [] : nil
  end
  if t == "ListNode"
    out = []
    n = 0
    while r && n < 200_000
      out << r.val; r = r.next; n += 1
    end
    return out
  end
  if t == "TreeNode"
    out = []
    q = [r]
    until q.empty?
      node = q.shift
      if node.nil?
        out << nil
        next
      end
      out << node.val
      q << node.left << node.right
    end
    out.pop while !out.empty? && out[-1].nil?
    return out
  end
  if lg_seq?(t)
    r = r.chars if r.is_a?(String) && lg_elem(t) == "character"
    return r.to_a.map { |x| lg_from(lg_elem(t), x) }
  end
  return r.to_f if t == "double"
  return (r ? true : false) if t == "boolean"
  return r.to_i if %w[integer long].include?(t) && r.is_a?(Float) && r == r.floor
  r
end

def lg_user_bt(e)
  bt = (e.backtrace || []).select { |l| l.include?("solution.rb") }.first(6)
  ([("#{e.class}: #{e.message}")] + bt).join("\n")
end

spec = JSON.parse(File.read(ARGV[0]))
src = File.read(ARGV[1])
begin
  eval(src, TOPLEVEL_BINDING, "solution.rb", 1)
rescue SyntaxError => e
  # detailed_message keeps syntax_suggest's hint but not the harness's own eval frames.
  lg_emit(-1, e.respond_to?(:detailed_message) ? e.detailed_message(highlight: false) : e.message, true)
  exit 0
rescue ScriptError, StandardError => e
  lg_emit(-1, lg_user_bt(e), true)
  exit 0
end

meta = spec["meta"]
name = spec["rb_name"]
ptypes = meta["params"].map { |p| p["type"] }
rtype = meta["return"]["type"]
oidx = (meta["output"] || {})["paramindex"]
main_obj = TOPLEVEL_BINDING.receiver

spec["tests"].each_with_index do |args, i|
  begin
    a = ptypes.zip(args).map { |t, x| lg_to(t, x) }
    r = main_obj.send(name, *a)
    out = oidx.nil? ? lg_from(rtype, r) : lg_from(ptypes[oidx], a[oidx])
    lg_emit(i, out)
  rescue NoMethodError => e
    if e.name.to_s == name && e.receiver.equal?(main_obj)
      lg_emit(i, "no method '#{name}' found: expected `def #{name}(...)`", true)
    else
      lg_emit(i, lg_user_bt(e), true)
    end
  rescue Exception => e
    lg_emit(i, lg_user_bt(e), true)
  end
end
