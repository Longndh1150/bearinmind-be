***

title: Deals - Create
slug: apis
headline: Create - HubSpot docs
canonical-url: '[https://developers.hubspot.com/docs/api-reference/latest/crm/objects/deals/create-deal](https://developers.hubspot.com/docs/api-reference/latest/crm/objects/deals/create-deal)'
---------------

## Deals - Create

```
POST https://api.hubapi.com/crm/objects/2026-03/{objectType}
POST /crm/objects/2026-03/{objectType} # Without base URL
```

### Supported products

Requires one of the following products or higher.
- Marketing Hub - Free
- Sales Hub - Free
- Service Hub - Free
- Content Hub - Free

### Required Scopes

This API requires one of the following scopes:
`crm.objects.deals.write`

### Authorizations

- Authorization (string, header, required): The access token received from the authorization server in the OAuth 2.0 flow.

### Path Parameters
​
- objectType (string, required)

### Body

application/json
Is the input object used to create a new CRM object, containing the properties to be set and optional associations to link the new record with other CRM objects.

- associations (object[], required):
  - associations.to (object, required): Contains the Id of a Public Object
    - associations.to.id (string, required): The unique ID of the object.
  - associations.types (object, []required):
    - associations.types.associationCategory (enum<string>, required): The category of the association, such as "HUBSPOT_DEFINED". Available options: `HUBSPOT_DEFINED`, `INTEGRATOR_DEFINED`, `USER_DEFINED`, `WORK` 
    - associations.types.associationTypeId (integer<int32>, required): The ID representing the specific type of association.
- properties (object, required): Key-value pairs for setting properties for the new object.
  - properties.{key} (string)

### Response

#### 201

application/json
successful operation

A simple public object.

- ​archived (boolean, required): Whether the object is archived.
- createdAt (string<date-time>, required): The timestamp when the object was created, in ISO 8601 format.
- id (string, required): The unique ID of the object.

​
properties
object,required
Key-value pairs representing the properties of the object.

Hide child attributes

​
properties.{key}
string
​
updatedAt
string<date-time>,required
The timestamp when the object was last updated, in ISO 8601 format.

​
archivedAt
string<date-time>
The timestamp when the object was archived, in ISO 8601 format.

​
objectWriteTraceId
string
Unique ID to identify each write operation, which will be returned with any errors to identify which request encountered which error.

​
propertiesWithHistory
object
Key-value pairs representing the properties of the object along with their history.

Hide child attributes

​
propertiesWithHistory.{key}
object[]
Hide child attributes

​
propertiesWithHistory.{key}.sourceType
string,required
The property type.

​
propertiesWithHistory.{key}.timestamp
string<date-time>,required
The timestamp when the property was updated, in ISO 8601 format.

​
propertiesWithHistory.{key}.value
string,required
The property value.

​
propertiesWithHistory.{key}.sourceId
string
The unique ID of the property.

​
propertiesWithHistory.{key}.sourceLabel
string
A human-readable label.

​
propertiesWithHistory.{key}.updatedByUserId
integer<int32>
The ID of the user who last updated the property.

​
url
string
URL to go to the object

Last modified on April 14, 2026

#### default

*/*


category
string,required
The error category

​
correlationId
string<uuid>,required
A unique identifier for the request. Include this value with any error reports or support tickets

Example:
"aeb5f871-7f07-4993-9211-075dc63e7cbf"

​
message
string,required
A human readable message describing the error along with remediation steps where appropriate

Example:
"An error occurred"

​
context
object
Context about the error condition

Hide child attributes

​
context.{key}
string[]
Example:
"{invalidPropertyName=[propertyValue], missingScopes=[scope1, scope2]}"

​
errors
object[]
further information about the error

Hide child attributes

​
errors.message
string,required
A human readable message describing the error along with remediation steps where appropriate

​
errors.code
string
The status code associated with the error detail

​
errors.context
object
Context about the error condition

Hide child attributes

​
errors.context.{key}
string[]
Example:
"{missingScopes=[scope1, scope2]}"

​
errors.in
string
The name of the field or parameter in which the error was found.

​
errors.subCategory
string
A specific category that contains more specific detail about the error

​
links
object
A map of link names to associated URIs containing documentation about the error or recommended remediation steps

Hide child attributes

​
links.{key}
string
​
subCategory
string
A specific category that contains more specific detail about the error

### Example

#### Request

```curl
curl --request POST \
  --url https://api.hubapi.com/crm/objects/2026-03/{objectType} \
  --header 'Authorization: Bearer <token>' \
  --header 'Content-Type: application/json' \
  --data '
{
  "associations": [
    {
      "to": {
        "id": "<string>"
      },
      "types": [
        {
          "associationCategory": "HUBSPOT_DEFINED",
          "associationTypeId": 123
        }
      ]
    }
  ],
  "properties": {}
}
'
```

```python
import requests

url = "https://api.hubapi.com/crm/objects/2026-03/{objectType}"

payload = {
    "associations": [
        {
            "to": { "id": "<string>" },
            "types": [
                {
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 123
                }
            ]
        }
    ],
    "properties": {}
}
headers = {
    "Authorization": "Bearer <token>",
    "Content-Type": "application/json"
}

response = requests.post(url, json=payload, headers=headers)

print(response.text)
```

```js
const options = {
  method: 'POST',
  headers: {Authorization: 'Bearer <token>', 'Content-Type': 'application/json'},
  body: JSON.stringify({
    associations: [
      {
        to: {id: '<string>'},
        types: [{associationCategory: 'HUBSPOT_DEFINED', associationTypeId: 123}]
      }
    ],
    properties: {}
  })
};

fetch('https://api.hubapi.com/crm/objects/2026-03/{objectType}', options)
  .then(res => res.json())
  .then(res => console.log(res))
  .catch(err => console.error(err));
```

#### Response

##### 201

```json
{
  "archived": true,
  "createdAt": "2023-11-07T05:31:56Z",
  "id": "<string>",
  "properties": {},
  "updatedAt": "2023-11-07T05:31:56Z",
  "archivedAt": "2023-11-07T05:31:56Z",
  "objectWriteTraceId": "<string>",
  "propertiesWithHistory": {},
  "url": "<string>"
}
```

##### default

```json
{
  "message": "Invalid input (details will vary based on the error)",
  "correlationId": "aeb5f871-7f07-4993-9211-075dc63e7cbf",
  "category": "VALIDATION_ERROR",
  "links": {
    "knowledge-base": "https://www.hubspot.com/products/service/knowledge-base"
  }
}
```
