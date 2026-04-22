# Python program to calculate the factorial of a number

# Import the math module for handling large numbers
import math

# Function to calculate the factorial of a number
def calculate_factorial(n):
    """
    Calculate the factorial of a given number.

    Args:
        n (int): The number to calculate the factorial of.

    Returns:
        int: The factorial of the given number.

    Raises:
        ValueError: If the input number is negative.
    """
    # Check if the input number is negative
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers.")

    # Use the math.prod function to calculate the factorial
    # This function is available in Python 3.8 and later
    # For earlier versions, you can use the math.prod function from the math module
    # or implement the factorial calculation manually
    return math.prod(range(1, n + 1))

# Function to calculate the factorial manually
def calculate_factorial_manual(n):
    """
    Calculate the factorial of a given number manually.

    Args:
        n (int): The number to calculate the factorial of.

    Returns:
        int: The factorial of the given number.

    Raises:
        ValueError: If the input number is negative.
    """
    # Check if the input number is negative
    if n < 0:
        raise ValueError("Factorial is not defined for negative numbers.")

    # Initialize the factorial to 1
    factorial = 1

    # Calculate the factorial manually
    for i in range(1, n + 1):
        factorial *= i

    return factorial

# Main function
def main():
    # Get the number to calculate the factorial of from the user
    num = int(input("Enter a number: "))

    # Calculate the factorial using the math.prod function
    try:
        factorial_math = calculate_factorial(num)
        print(f"The factorial of {num} using math.prod is: {factorial_math}")
    except ValueError as e:
        print(e)

    # Calculate the factorial manually
    try:
        factorial_manual = calculate_factorial_manual(num)
        print(f"The factorial of {num} manually is: {factorial_manual}")
    except ValueError as e:
        print(e)

# Run the main function
if __name__ == "__main__":
    main()
