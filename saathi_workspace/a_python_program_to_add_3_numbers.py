# Import the necessary module for handling user input
import sys

# Define a function to get and validate user input
def get_number(prompt):
    """
    Get a number from the user and validate it.

    Args:
        prompt (str): The prompt to display to the user.

    Returns:
        float: The validated number.
    """
    while True:
        try:
            # Attempt to convert the user's input to a float
            return float(input(prompt))
        except ValueError:
            # If the input cannot be converted to a float, display an error message
            print("Invalid input. Please enter a number.")

# Define the main function
def main():
    """
    The main function of the program.

    This function gets three numbers from the user, calculates their sum, and displays the result.
    """
    # Get the three numbers from the user
    num1 = get_number("Enter the first number: ")
    num2 = get_number("Enter the second number: ")
    num3 = get_number("Enter the third number: ")

    # Calculate the sum of the three numbers
    total = num1 + num2 + num3

    # Display the result
    print(f"The sum of {num1}, {num2}, and {num3} is: {total}")

# Check if the program is being run directly (not being imported)
if __name__ == "__main__":
    # Call the main function
    main()

#
