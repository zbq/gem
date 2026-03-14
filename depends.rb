require 'optparse'

def __walk(chain, item, getter, &block)
  chain << item
  next_items = getter.call(item)
  if next_items.length != 0 then
    next_items.each do |next_item|
      if chain.include?(next_item) then
        yield chain.dup, next_item # dead lock
      else
        __walk(chain, next_item, getter, &block)
      end
    end
  elsif chain.length != 1 then
    yield chain.dup, nil
  end
  chain.pop
end

def walk_depends(depends, item, &block)
  chain = []
  getter = lambda {|item| depends[item]}
  __walk(chain, item, getter, &block)
end

def walk_rdepends(depends, item, &block)
  chain = []
  getter = lambda { |item|
    rdeps = Set.new
    depends.each { |k, v|
      if v.include?(item) then
        rdeps.add(k)
      end
    }
    return rdeps
  }
  __walk(chain, item, getter, &block)
end

def __dry_clean(cleaned, depends, tops, items)
  items.each do |item|
    depends.delete(item)
    cleaned.add(item)
  end
  tops2 = (depends.keys.to_set - depends.values.to_set.flatten)
  new = tops2 - tops
  if new.length != 0 then
    __dry_clean(cleaned, depends, tops2, new)
  end
end

def dry_clean(depends, items)
  cleaned = Set.new
  tops = (depends.keys.to_set - depends.values.to_set.flatten)
  items.each do |item|
    if not tops.include?(item) then
      puts "'#{item}' is not a top level item"
      return cleaned
    end
  end
  __dry_clean(cleaned, depends, tops, items)
  return cleaned
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
  parser.on("-c", "--dry-clean=ITEMS", Array, "show items and all depends that are cleanable") do |v|
    options[:dry_clean] = v
  end
end.parse!

if ARGV.size != 1 then
  puts "one dependency-file is required"
  exit 1
end

depends = Hash.new { |h, k| h[k] = Set.new() }
File.open(ARGV[0]) do |file|
  file.each_line do |line|
    parts = line.split
    if parts.size == 3 and parts[1] == "->" then
      depends[parts[0]].add(parts[2])
      depends[parts[2]] # ensure that every item exist in keys
    end
  end
end

if options[:top] then
  (depends.keys.to_set - depends.values.to_set.flatten).each do |item|
    puts item
  end
elsif options[:depends] then
  depends.fetch(options[:depends], Set.new()).each do |item|
    puts item
  end
elsif options[:all_depends] then
  if options[:verbose] then
    walk_depends(depends, options[:all_depends]) do |ch, deadlock|
      if deadlock then
        puts "#{ch.join(" -> ")} -> #{deadlock} (DEAD LOCK)"
      else
        puts "#{ch.join(" -> ")}"
      end
    end
  else
    all = Set.new()
    walk_depends(depends, options[:all_depends]) do |ch, _|
      all.merge(ch)
    end
    all.delete(options[:all_depends]).sort.each do |item|
      puts item
    end
  end
elsif options[:rdepends] then
  depends.each do |k, v|
    if v.include?(options[:rdepends])
      puts k
    end
  end
elsif options[:all_rdepends] then
  if options[:verbose] then
    walk_rdepends(depends, options[:all_rdepends]) do |ch, deadlock|
      if deadlock then
        puts "#{ch.join(" <- ")} <- #{deadlock} (DEAD LOCK)"
      else
        puts "#{ch.join(" <- ")}"
      end
    end
  else
    all = Set.new()
    walk_rdepends(depends, options[:all_rdepends]) do |ch, _|
      all.merge(ch)
    end
    all.delete(options[:all_rdepends]).sort.each do |item|
      puts item
    end
  end
elsif options[:dry_clean] then
  dry_clean(depends, options[:dry_clean]).each do |item|
    puts item
  end
end

