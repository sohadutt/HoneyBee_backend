# HoneyBee Backend API

Django REST Framework backend for the HoneyBee matching app. The API uses JWT auth, stores profile images in Vercel Blob, and returns blurred profile photos for public match/recommendation surfaces.

## Base URL

Local development:

```text
http://localhost:8000/api/
```

All authenticated requests must include:

```http
Authorization: Bearer <access_token>
```

JSON requests should use:

```http
Content-Type: application/json
```

Picture upload requests should use:

```http
Content-Type: multipart/form-data
```

## Authentication

### Register

```http
POST /api/auth/register/
```

Creates a new user account.

Request body:

```json
{
  "username": "maya",
  "email": "maya@example.com",
  "password": "StrongPassword123!",
  "phone": "+15555550123",
  "country": "US",
  "first_name": "Maya",
  "last_name": "Stone",
  "date_of_birth": "1998-04-20",
  "bio": "Short profile bio",
  "match_radius_km": 50,
  "match_dominance_preferences": ["switch"],
  "sex": "female",
  "orientation": "bisexual",
  "dominance": ["switch"],
  "kink_ids": [1, 2]
}
```

Required fields:

```text
username, email, password, phone, country, first_name, sex, orientation
```

Response `201`:

```json
{
  "id": 1,
  "username": "maya",
  "email": "maya@example.com",
  "phone": "+15555550123",
  "country": "US",
  "date_of_birth": "1998-04-20",
  "age": 28,
  "bio": "Short profile bio",
  "match_radius_km": 50,
  "match_dominance_preferences": ["switch"],
  "tier": 0,
  "first_name": "Maya",
  "last_name": "Stone",
  "is_verified": false,
  "sex": "female",
  "orientation": "bisexual",
  "blurred_pictures_urls": [],
  "lowres_pictures_urls": [],
  "highres_pictures_urls": [],
  "dominance": ["switch"],
  "kinks": [],
  "created_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z"
}
```

### Login

```http
POST /api/auth/login/
```

Request body:

```json
{
  "email": "maya@example.com",
  "password": "StrongPassword123!"
}
```

Response `200`:

```json
{
  "refresh": "<refresh_token>",
  "access": "<access_token>"
}
```

### Refresh Token

```http
POST /api/auth/refresh/
```

Request body:

```json
{
  "refresh": "<refresh_token>"
}
```

Response `200`:

```json
{
  "access": "<new_access_token>"
}
```

### Logout

```http
POST /api/auth/logout/
```

Authentication required.

Request body:

```json
{
  "refresh": "<refresh_token>"
}
```

Response `204`: empty body.

If refresh token blacklisting is not enabled, the endpoint still returns `204` after the client discards its tokens.

## Profile

### Get My Profile

```http
GET /api/profile/
GET /api/users/me/
```

Authentication required.

Response `200`:

```json
{
  "id": 1,
  "username": "maya",
  "email": "maya@example.com",
  "phone": "+15555550123",
  "country": "US",
  "date_of_birth": "1998-04-20",
  "age": 28,
  "bio": "Short profile bio",
  "match_radius_km": 50,
  "match_dominance_preferences": ["switch"],
  "tier": 0,
  "first_name": "Maya",
  "last_name": "Stone",
  "is_verified": false,
  "sex": "female",
  "orientation": "bisexual",
  "blurred_pictures_urls": ["https://blob.vercel-storage.com/profile-pictures/1/a-blurred.webp"],
  "lowres_pictures_urls": ["https://blob.vercel-storage.com/profile-pictures/1/a-blurred.webp"],
  "highres_pictures_urls": ["https://blob.vercel-storage.com/profile-pictures/1/a-highres.webp"],
  "dominance": ["switch"],
  "kinks": [
    {
      "id": 1,
      "name": "Example",
      "description": "Example description"
    }
  ],
  "created_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z"
}
```

### Update My Profile

```http
PATCH /api/users/me/
```

Authentication required. Send only fields that should change.

Request body:

```json
{
  "bio": "Updated bio",
  "match_radius_km": 80,
  "match_dominance_preferences": ["dominant", "switch"],
  "dominance": ["switch"],
  "kink_ids": [1, 3]
}
```

Response `200`: full private user profile.

## Profile Pictures

Users can save up to 6 profile pictures. Uploads support common Pillow image formats plus HEIF/HEIC through `pillow-heif`. Every uploaded image is converted into two WebP files:

```text
blurred_pictures_urls: public blurred image URLs
highres_pictures_urls: private owner-only high-resolution image URLs
```

Public match and recommendation responses only include `blurred_pictures_urls`.

### Get My Pictures

```http
GET /api/users/me/pictures/
```

Authentication required.

Response `200`:

```json
{
  "blurred_pictures_urls": [
    "https://blob.vercel-storage.com/profile-pictures/1/a-blurred.webp"
  ],
  "highres_pictures_urls": [
    "https://blob.vercel-storage.com/profile-pictures/1/a-highres.webp"
  ]
}
```

### Add Pictures

```http
POST /api/users/me/pictures/
```

Authentication required. Appends uploaded pictures to the existing list.

Form data:

```text
pictures: <file>
pictures: <file>
```

You may also upload one file using:

```text
picture: <file>
```

Response `201`:

```json
{
  "blurred_pictures_urls": [
    "https://blob.vercel-storage.com/profile-pictures/1/a-blurred.webp"
  ],
  "highres_pictures_urls": [
    "https://blob.vercel-storage.com/profile-pictures/1/a-highres.webp"
  ]
}
```

Error `400` when no file is uploaded, a non-image is uploaded, an invalid image is uploaded, or the user would exceed 6 total pictures:

```json
{
  "detail": "Profiles can have at most 6 pictures."
}
```

### Replace All Pictures

```http
PUT /api/users/me/pictures/
```

Authentication required. Replaces the full picture set with the uploaded files.

Form data:

```text
pictures: <file>
pictures: <file>
```

Response `201`: same shape as get pictures.

### Delete One Picture

```http
DELETE /api/users/me/pictures/
```

Authentication required. Delete by zero-based index:

```json
{
  "index": 0
}
```

Or by URL:

```json
{
  "highres_url": "https://blob.vercel-storage.com/profile-pictures/1/a-highres.webp"
}
```

```json
{
  "blurred_url": "https://blob.vercel-storage.com/profile-pictures/1/a-blurred.webp"
}
```

Response `200`: remaining picture URLs.

Error `404`:

```json
{
  "detail": "Picture not found."
}
```

## Kinks

### List Kinks

```http
GET /api/kinks/
```

Authentication required.

Response `200`:

```json
[
  {
    "id": 1,
    "name": "Example",
    "description": "Example description"
  }
]
```

### Create Kink

```http
POST /api/kinks/
```

Authentication required.

Request body:

```json
{
  "name": "Example",
  "description": "Example description"
}
```

Response `201`:

```json
{
  "id": 1,
  "name": "Example",
  "description": "Example description"
}
```

### Retrieve, Update, Delete Kink

```http
GET /api/kinks/{id}/
PATCH /api/kinks/{id}/
PUT /api/kinks/{id}/
DELETE /api/kinks/{id}/
```

Authentication required. `PATCH` and `PUT` use the same fields as create.

## Users

### List Users

```http
GET /api/users/
```

Authentication required.

Response `200`: list of private user serializer objects. This is an internal/admin-style endpoint and includes `highres_pictures_urls`.

### Create User

```http
POST /api/users/
```

Same request and response shape as `POST /api/auth/register/`.

### Retrieve, Update, Delete User

```http
GET /api/users/{id}/
PATCH /api/users/{id}/
PUT /api/users/{id}/
DELETE /api/users/{id}/
```

Authentication required. Router-level user endpoints currently use the private user serializer.

## Recommendations

### List Recommendations

```http
GET /api/recommendations/
GET /api/recommendations/?limit=20
GET /api/recommendations/?limit=20&save_matches=true
```

Authentication required.

Query params:

```text
limit: optional integer, defaults to 20, maximum 50
save_matches: optional "true"; saves returned users into matches
```

Response `200`:

```json
[
  {
    "user": {
      "id": 2,
      "first_name": "Riley",
      "age": 29,
      "bio": "Public profile bio",
      "country": "US",
      "sex": "female",
      "orientation": "bisexual",
      "dominance": ["dominant"],
      "blurred_pictures_urls": [
        "https://blob.vercel-storage.com/profile-pictures/2/a-blurred.webp"
      ],
      "kinks": [
        {
          "id": 1,
          "name": "Example",
          "description": "Example description"
        }
      ]
    },
    "score": 83,
    "shared_kinks": ["Example"],
    "dominance_score": 24,
    "orientation_score": 19
  }
]
```

## Matches

### List Matches

```http
GET /api/matches/
```

Authentication required.

Response `200`:

```json
[
  {
    "id": 1,
    "matched_user": {
      "id": 2,
      "first_name": "Riley",
      "age": 29,
      "bio": "Public profile bio",
      "country": "US",
      "sex": "female",
      "orientation": "bisexual",
      "dominance": ["dominant"],
      "blurred_pictures_urls": [
        "https://blob.vercel-storage.com/profile-pictures/2/a-blurred.webp"
      ],
      "kinks": [
        {
          "id": 1,
          "name": "Example",
          "description": "Example description"
        }
      ]
    },
    "score": 83,
    "kinks_in_common_count": 1,
    "common_kinks": ["Example"],
    "matched_at": "2026-05-08T10:00:00Z"
  }
]
```

### Retrieve Match

```http
GET /api/matches/{id}/
```

Authentication required. Response shape is the same as one list item.

## Conversations

### List Conversations

```http
GET /api/conversations/
```

Authentication required.

Response `200`:

```json
[
  {
    "id": 1,
    "public_id": "thread_public_id",
    "participants": [
      {
        "id": 1,
        "first_name": "Maya",
        "age": 28,
        "bio": "Short profile bio",
        "country": "US",
        "sex": "female",
        "orientation": "bisexual",
        "dominance": ["switch"],
        "blurred_pictures_urls": [
          "https://blob.vercel-storage.com/profile-pictures/1/a-blurred.webp"
        ],
        "kinks": []
      }
    ],
    "provider_thread_id": null,
    "messages": [],
    "created_at": "2026-05-08T10:00:00Z",
    "updated_at": "2026-05-08T10:00:00Z"
  }
]
```

### Retrieve Conversation

```http
GET /api/conversations/{id}/
```

Authentication required. Response shape is the same as one list item.

### Send Message

```http
POST /api/conversations/send/
```

Authentication required.

Request body:

```json
{
  "recipient_id": 2,
  "body": "Hey, nice to meet you."
}
```

Response `201`:

```json
{
  "id": 1,
  "public_id": "thread_public_id",
  "participants": [],
  "provider_thread_id": null,
  "messages": [
    {
      "id": 1,
      "conversation": 1,
      "sender": 1,
      "recipient": 2,
      "direction": "outbound",
      "body": "Hey, nice to meet you.",
      "provider_message_id": null,
      "delivered_at": null,
      "read_at": null,
      "created_at": "2026-05-08T10:00:00Z"
    }
  ],
  "created_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z",
  "message_id": 1
}
```

## Messaging Webhook

### Receive Messaging Event

```http
POST /api/webhooks/messaging/
```

Authentication not required. If `MESSAGING_WEBHOOK_SECRET` is set, send the HMAC header:

```http
X-Honeybee-Signature: sha256=<hex_digest>
```

Request body:

```json
{
  "event_id": "provider-event-123",
  "event_type": "message.received",
  "provider": "generic",
  "sender_external_id": "external-user-1",
  "recipient_external_id": "external-user-2",
  "body": "Inbound message",
  "message_id": "provider-message-123"
}
```

Response `202`:

```json
{
  "event_id": "provider-event-123",
  "event_type": "message.received",
  "provider": "generic",
  "payload": {
    "event_id": "provider-event-123",
    "event_type": "message.received",
    "provider": "generic",
    "sender_external_id": "external-user-1",
    "recipient_external_id": "external-user-2",
    "body": "Inbound message",
    "message_id": "provider-message-123"
  },
  "processed_at": "2026-05-08T10:00:00Z",
  "created_at": "2026-05-08T10:00:00Z"
}
```

Duplicate event response `200`:

```json
{
  "detail": "Event already processed."
}
```

Invalid signature response `401`:

```json
{
  "detail": "Invalid webhook signature."
}
```

## Field Values

Country choices:

```text
IN, US, UK, CA, AU, DE, FR, JP, CN, BR
```

Sex choices:

```text
male, female, ftm, mtf, non_binary, other
```

Orientation choices:

```text
straight, gay, lesbian, bisexual, asexual, pansexual, queer, other
```

Dominance choices:

```text
dominant, submissive, switch, top, bottom, other
```

Tier values:

```text
0: Free
1: Pro
2: Premium
```

## Common Error Shapes

Validation errors return `400` with field-level details:

```json
{
  "email": ["user with this email already exists."],
  "password": ["This password is too common."]
}
```

Authentication errors return `401`:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

Permission errors return `403`:

```json
{
  "detail": "You do not have permission to perform this action."
}
```

Not found errors return `404`:

```json
{
  "detail": "Not found."
}
```

## Local Development

Install dependencies and run migrations:

```bash
uv sync
uv run python manage.py migrate
```

Run the API:

```bash
uv run python manage.py runserver
```

Run checks and tests:

```bash
uv run python manage.py check
uv run python manage.py test
```
