from pydantic import BaseModel
import json

# test parsing json into pydantic BaseModel

class TestModel(BaseModel):
    name: str
    age: int
    active: bool = True
    
test_str_1 = '''
{
    "name": "Alice",
    "age": 30,
    "active": false
}
'''
test_str_2 = '''
{
    "name": "Bob",
    "age": "25"
}
'''
test_str_3 = '''
{
    "name": "Charlie"
}
'''
test_str_4 = '''
{
    "name": "Diana",
    "age": "twenty-five",
    "other_field": 123
}
'''

class OuterModel(BaseModel):
    id: int
    data: TestModel
    
test_str_5 = '''
{
    "id": 1,
    "data": {
        "name": "Eve",
        "age": 28,
        "active": true
    }
}
'''

def test_parsing():
    # Test parsing valid JSON string
    model_1 = TestModel.model_validate_json(test_str_1)
    assert model_1.name == "Alice"
    assert model_1.age == 30
    assert model_1.active == False
    
    # Test parsing JSON string with missing optional field
    model_2 = TestModel.model_validate_json(test_str_2)
    assert model_2.name == "Bob"
    assert model_2.age == 25
    assert model_2.active == True  # default value
    
    # Test parsing JSON string with missing required field
    try:
        model_3 = TestModel.model_validate_json(test_str_3)
        assert False, "Expected validation error for missing required field"
    except Exception as e:
        print("Caught expected exception for test_str_3:", e)
        
    # Test parsing JSON string with invalid field type
    try:
        model_4 = TestModel.model_validate_json(test_str_4)
        assert False, "Expected validation error for invalid field type"
    except Exception as e:
        print("Caught expected exception for test_str_4:", e)
        
    # Test parsing nested model
    outer_model = OuterModel.model_validate_json(test_str_5)
    assert outer_model.id == 1
    assert outer_model.data.name == "Eve"
    assert outer_model.data.age == 28
    assert outer_model.data.active == True

    print("All tests passed.")
    
if __name__ == "__main__":
    test_parsing()