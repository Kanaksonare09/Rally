import jwt

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlqeXp6b3RrdmZ4eGR4c2d0d2t2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc3MTg4NTcsImV4cCI6MjEwMzI5NDg1N30.fi44j7-gkXtvZuQKxLvkpyZ-X40vgfsdRJ428Bn0fsY"
secret = "09673179-b284-450c-967c-6776f559b775"
decode_kwargs = {"issuer": "https://yjyzzotkvfxxdxsgtwkv.supabase.co/auth/v1"}

try:
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience="authenticated",
        **decode_kwargs,
    )
except Exception as e:
    print(type(e).__name__, str(e))
