# Factorial Calculator Program
# Author: Elite Software Engineer
# Description: This program calculates the factorial of a given number.

# Import the math module for handling large numbers
import math

def calculate_factorial(num):
    """
    Calculate the factorial of a given number.

    Args:
        num (int): The number to calculate the factorial for.

    Returns:
        int: The factorial of the given number.

    Raises:
        ValueError: If the input number is negative.
    """
    # Check if the input number is negative
    if num < 0:
        raise ValueError("Factorial is not defined for negative numbers.")

    # Use the math.prod function to calculate the factorial
    # This function is available in Python 3.8 and later
    # For earlier versions, you can use the math.prod function from the math module
    # or implement the factorial calculation manually
    try:
        return math.prod(range(1, num + 1))
    except TypeError:
        # If the input number is not an integer, raise a TypeError
        raise TypeError("Input number must be an integer.")

def main():
    """
    The main function of the program.

    This function prompts the user to enter a number, calculates its factorial,
    and prints the result.
    """
    # Prompt the user to enter a number
    num = input("Enter a number: ")

    # Try to convert the input to an integer
    try:
        num = int(num)
    except ValueError:
        # If the input cannot be converted to an integer, print an error message
        print("Invalid input. Please enter a whole number.")
        return

    # Calculate the factorial of the input number
    try:
        factorial = calculate_factorial(num)
    except (ValueError, TypeError) as e:
        # If an error occurs during the calculation, print the error message
        print(f"Error: {e}")
        return

    # Print the result
    print(f"The factorial of {num} is: {factorial}")

if __name__ == "__main__":
    main()
