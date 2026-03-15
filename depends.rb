require 'optparse'

def __walk(chain, item, iterator, &block)
  chain << item
  next_items = iterator.call(item)
  if next_items.empty? then
    yield chain.dup, nil
  end
  next_items.each do |next_item|
    if chain.include?(next_item) then
      yield chain.dup, next_item # dead lock
    else
      __walk(chain, next_item, iterator, &block)
    end
  end
  chain.pop
end

def walk_depends(depends, item)
  chain = []
  iterator = lambda {|item| depends[item]}
  __walk(chain, item, iterator) do |ch, deadlock|
    yield ch, deadlock if ch.length != 1
  end
end

def get_rdepends(depends, item)
  rdeps = Set.new
  depends.each do |k, v|
    if v.include?(item)
      rdeps.add(k)
    end
  end
  return rdeps
end

def walk_rdepends(depends, item)
  chain = []
  iterator = lambda { |item|
    return get_rdepends(depends, item)
  }
  __walk(chain, item, iterator) do |ch, deadlock|
    yield ch, deadlock if ch.length != 1
  end
end

def get_tops(depends)
  # item no one depends on
  items = depends.keys.to_set
  depends.each_value do |deps|
    items.subtract(deps)
  end
  return items
end

def __dry_clean(cleaned, depends, tops, items)
  items.each do |item|
    depends.delete(item)
    cleaned.add(item)
  end
  new_tops = get_tops(depends)
  delta = new_tops - tops
  if delta.length != 0 then
    __dry_clean(cleaned, depends, new_tops, delta)
  end
end

def dry_clean(depends, items)
  tops = get_tops(depends)
  items.each do |item|
    if not tops.include?(item) then
      puts "'#{item}' is not a top level item"
      return Set.new
    end
  end
  cleaned = Set.new
  __dry_clean(cleaned, depends, tops, items)
  return cleaned
end

# a -> b c d
def read_depends(filename)
  depends = Hash.new
  File.open(filename) do |file|
    file.each_line do |line|
      item, mark, *deps = line.split
      if mark == "->" and not deps.empty? then
        depends[item] = depends.fetch(item, Set.new).union(deps)
        deps.each do |dep|
          depends[dep] = depends.fetch(dep, Set.new)
        end
      end
    end
  end
  return depends
end

options = {}
OptionParser.new do |parser|
  parser.banner = "Usage: depends.rb [options] dependency-file"

  parser.on("-t", "--top", "show top level items") do |v|
    options[:top] = true
  end
  parser.on("-v", "--verbose", "show verbosely") do |v|
    options[:verbose] = true
  end
  parser.on("-d", "--depends=ITEM", "show depends of item") do |v|
    options[:depends] = v
  end
  parser.on("-D", "--all-depends=ITEM", "show all (recursive) depends of item") do |v|
    options[:all_depends] = v
  end
  parser.on("-r", "--rdepends=ITEM", "show reversed depends of item") do |v|
    options[:rdepends] = v
  end
  parser.on("-R", "--all-rdepends=ITEM", "show all (recursive) reversed depends of item") do |v|
    options[:all_rdepends] = v
  end
  parser.on("-c", "--dry-clean=ITEMS", Array, "dry clean items and there private depends") do |v|
    options[:dry_clean] = v
  end
  parser.on("-C", "--dry-clean-list=FILE", "dry clean items (from FILE) and there private depends") do |v|
    options[:dry_clean_list] = v
  end
end.parse!

if ARGV.size != 1 then
  puts "one dependency-file is required"
  exit 1
end

def ensure_exist(depends, item)
  if not depends.include?(item) then
    puts "'#{item}' is not exist"
    exit 1
  end
end

depends = read_depends(ARGV[0])
if options[:top] then
  get_tops(depends).sort.each do |item|
    puts item
  end
elsif options[:depends] then
  item = options[:depends]
  ensure_exist(depends, item)
  depends[item].each do |dep|
    puts dep
  end
elsif options[:all_depends] then
  item = options[:all_depends]
  ensure_exist(depends, item)
  if options[:verbose] then
    walk_depends(depends, item) do |ch, deadlock|
      if deadlock then
        puts "#{ch.join(" -> ")} -> #{deadlock} (DEAD LOCK)"
      else
        puts "#{ch.join(" -> ")}"
      end
    end
  else
    deps = Set.new()
    walk_depends(depends, item) do |ch, _|
      deps.merge(ch)
    end
    deps.delete(item).sort.each do |dep|
      puts dep
    end
  end
elsif options[:rdepends] then
  item = options[:rdepends]
  ensure_exist(depends, item)
  get_rdepends(depends, item).each do |rdep|
    puts rdep
  end
elsif options[:all_rdepends] then
  item = options[:all_rdepends]
  ensure_exist(depends, item)
  if options[:verbose] then
    walk_rdepends(depends, item) do |ch, deadlock|
      if deadlock then
        puts "#{ch.join(" <- ")} <- #{deadlock} (DEAD LOCK)"
      else
        puts "#{ch.join(" <- ")}"
      end
    end
  else
    rdeps = Set.new()
    walk_rdepends(depends, item) do |ch, _|
      rdeps.merge(ch)
    end
    rdeps.delete(item).sort.each do |rdep|
      puts rdep
    end
  end
elsif options[:dry_clean] then
  items = options[:dry_clean]
  items.each do |item|
    ensure_exist(depends, item)
  end
  dry_clean(depends, items).each do |item|
    puts item
  end
elsif options[:dry_clean_list] then
  items = IO.readlines(options[:dry_clean_list]).collect {|line| line.chomp("\n")}
  items.each do |item|
    ensure_exist(depends, item)
  end
  dry_clean(depends, items).each do |item|
    puts item
  end
end

