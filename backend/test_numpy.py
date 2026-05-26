import numpy as np

# Test that numpy was auto-installed
print("numpy version:", np.__version__)

# Create a 3x3 matrix
matrix = np.array([
    [1, 2, 3],
    [4, 5, 6],
    [7, 8, 9]
])

print("\nMatrix:")
print(matrix)

print("\nTransposed:")
print(matrix.T)

print("\nSum of all elements:", np.sum(matrix))
print("Mean:", np.mean(matrix))
print("Max:", np.max(matrix))
print("Min:", np.min(matrix))

# Multiply matrix by itself
print("\nMatrix squared (element-wise):")
print(matrix ** 2)

print("\nnumpy auto-install test complete!")
