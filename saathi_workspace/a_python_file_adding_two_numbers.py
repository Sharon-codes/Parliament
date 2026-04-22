# Import the necessary module for getting user input
import sys

# Define a function to add two numbers
def add_numbers(num1, num2):
    """
    This function takes two numbers as input and returns their sum.

    Args:
        num1 (float): The first number to add.
        num2 (float): The second number to add.

    Returns:
        float: The sum of num1 and num2.
    """
    return num1 + num2

# Define a function to get user input
def get_user_input(prompt):
    """
    This function gets a number from the user and returns it as a float.

    Args:
        prompt (str): The prompt to display to the user.

    Returns:
        float: The number entered by the user.
    """
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            print("Invalid input. Please enter a number.")

# Main program
def main():
    # Get the two numbers from the user
    num1 = get_user_input("Enter the first number: ")
    num2 = get_user_input("Enter the second number: ")

    # Add the two numbers together
    result = add_numbers(num1, num2)

    # Display the result
    print(f"The sum of {num1} and {num2} is: {result}")

# Run the main program
if __name__ == "__main__":
    main()

#
