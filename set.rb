#!/usr/bin/ruby

def read(filename)
  lines = Set.new
  File.open(filename) do |file|
    file.each_line do |line|
      line.chomp!
      lines.add(line) unless line.empty?
    end
  end
  return lines
end

if ARGV.count != 3 or not ['|', '&', '-', '^'].include?(ARGV[1]) then
  $stderr.puts "Usage: set.rb file1 '|' | '&' | '-' | '^' file2"
  exit 1
end

set1 = read(ARGV[0])
set2 = read(ARGV[2])
result = set1.send(ARGV[1], set2)
result.sort.each do |line|
  puts line
end
