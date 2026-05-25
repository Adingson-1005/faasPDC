#!/bin/bash
echo "Hello from FaaS Runner - Bash!"
echo "2 + 2 = $((2 + 2))"
echo "Current date: $(date)"

for name in Alice Bob Charlie; do
  echo "Hello, $name!"
done
